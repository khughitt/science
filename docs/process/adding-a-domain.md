# Adding a Domain to Science

**Audience:** AI agent executing the process
**Reference implementation:** biology (biology/translational science)

This document describes the end-to-end process for adding a new scientific domain
to the science knowledge model. A "domain" means a community ontology (or
hand-built catalog) that provides entity types and relation predicates for a
field of study.

The process has two parts:

1. **Domain research & ontology selection** — identify, evaluate, and curate the
   right ontology. This requires judgment.
2. **Implementation checklist** — create files, wire integration, write tests.
   This is mechanical.

The biology implementation is the canonical example. When in doubt, look at
what biology does and follow the same pattern.

---

## Part 1: Domain Research & Ontology Selection

### Stage 1: Domain scoping

Define the domain's boundaries before searching for ontologies.

1. **Entity types** — What kinds of things do users model in this domain?
   List 10-20 concrete entity types a researcher would want to create.
   (Biology example: gene, protein, disease, pathway, cell, organism.)

2. **Relation predicates** — What relationships matter between those entities?
   List 10-15 key predicates.
   (Biology example: interacts_with, causes, treats, expressed_in, part_of.)

3. **Boundaries** — What's adjacent but out of scope? Explicitly exclude
   neighboring domains to avoid scope creep. The user can always add another
   domain later.

4. **CURIE landscape** — What identifier systems are used in this domain?
   (Biology example: NCBIGene, UniProtKB, ENSEMBL, CLINVAR.)
   These become `curie_prefixes` in the catalog and drive external reference
   detection.

Write the scoping results as a short markdown section in the domain's design
spec (e.g., `doc/specs/YYYY-MM-DD-<domain>-ontology-design.md`). This is the
input to Stage 2.

### Stage 2: Ontology landscape survey

Search for community ontologies that cover the scoped domain. Where to look:

| Source | URL | Notes |
|--------|-----|-------|
| OBO Foundry | https://obofoundry.org/ | Life sciences focus, high quality standards |
| BioPortal | https://bioportal.bioontology.org/ | Broad biomedical ontology repository |
| Linked Open Vocabularies | https://lov.linkeddata.es/ | General-purpose linked data vocabularies |
| schema.org | https://schema.org/ | Web-oriented, sometimes has domain extensions |
| Domain data repositories | varies | Look at what vocabularies major databases in the field use |
| GitHub / academic papers | varies | Search for "<domain> ontology" or "<domain> data model" |

For each candidate ontology, record:

```markdown
- **Name**: e.g., Biolink Model
- **Maintainer**: e.g., Biolink Consortium / NCATS
- **Scope**: what it covers
- **Size**: approximate number of entity types and predicates
- **Format**: OWL, LinkML, SKOS, YAML, JSON-LD, etc.
- **Last release**: date and version
- **Adoption**: used by which databases/tools
- **License**: permissive? attribution-only?
- **URL**: source repository or specification
```

### Stage 3: Ontology evaluation & selection

Evaluate candidates using this rubric. Score each criterion 1-3 (1 = poor,
3 = strong):

| Criterion | Weight | What to check |
|-----------|--------|---------------|
| **Coverage** | High | Does it define the entity types and predicates identified in Stage 1? Gaps are acceptable if small; major gaps are disqualifying. |
| **Adoption** | High | Is it used by major databases, tools, or standards bodies in the domain? Widespread adoption means the vocabulary is stable and understood. |
| **Maintenance** | Medium | Actively maintained? Released in the last 2 years? An abandoned ontology is a risk. |
| **Format compatibility** | Medium | Can terms be extracted programmatically? LinkML and OWL are ideal (parseable with existing tooling). YAML/JSON also workable. PDF-only specs are last resort. |
| **Size** | Low | A very large ontology (10k+ terms) is fine if it can be filtered. A very small one (<20 terms) may not justify the integration cost. |

**Decision branches:**

```
Is there one dominant, well-adopted ontology?
├── YES → Use it. Proceed to Stage 4.
├── MULTIPLE complementary ontologies exist
│   └── Pick the one with best coverage + adoption as primary.
│       Note the others in the design spec for future consideration.
│       Proceed to Stage 4 with the primary.
└── NO suitable ontology exists
    └── Create a hand-built catalog using the same YAML schema.
        Mark it as `source_url: "project-authored"` in the registry.
        Follow the same catalog format so it's a drop-in replacement
        if a community ontology emerges later.
        Proceed to Stage 4 (but skip the extraction script —
        author the catalog YAML directly).
```

### Stage 4: Catalog curation

Once the ontology is chosen, produce the term catalog.

1. **Write the extraction script** (if using a community ontology):
   - Create `scripts/extract_<ontology>_catalog.py`
   - Follow `scripts/extract_biology_catalog.py` as the template
   - The script fetches/parses the ontology source and outputs `catalog.yaml`
   - Key decisions embedded in the script:
     - **Entity type filter**: which classes to include (biology: non-abstract
       descendants of NamedThing)
     - **Predicate filter**: which slots/properties to include (biology: those
       with NamedThing range)
     - **Name normalization**: CamelCase → snake_case (follow `_camel_to_snake`
       in the biology script)
     - **Description truncation**: cap at 200 chars

2. **Mark recommended terms**:
   - `recommended: true` terms appear in suggestion output; the full catalog
     is always available for validation
   - Target: **20-50 entity types**, **15-35 predicates**
   - Selection criteria: commonly used in the domain, likely to appear in
     a typical research project, not overly specialized
   - Define the recommended sets as constants in the extraction script
     (see `RECOMMENDED_ENTITY_TYPES` and `RECOMMENDED_PREDICATES` in the
     biology script)

3. **Map CURIE prefixes**:
   - For each entity type, list the identifier systems whose CURIEs reference
     entities of that type
   - These drive `external_prefixes()` in `sources.py` and the suggestion
     mechanism's CURIE prefix matching
   - If the ontology source includes `id_prefixes` (as biology does), extract
     them automatically

4. **Run the extraction script** and inspect the output:
   - Verify entity type and predicate counts are reasonable
   - Spot-check a few entries for correct names, descriptions, prefixes
   - Ensure the output parses as valid `OntologyCatalog` via the Pydantic model

---

## Part 2: Implementation Checklist

Execute these steps in order. Each step has a **gate** — a validation that must
pass before proceeding. Part 1 determined *what* to build; Part 2 is *how* to
build it. Decisions from Stage 4 (recommended terms, CURIE prefixes, filters)
feed directly into Step 1.

### Step 1: Extraction script

**Create:** `scripts/extract_<ontology>_catalog.py`

Pattern to follow: `scripts/extract_biology_catalog.py`

The script must:
- Define `<ONTOLOGY>_VERSION` and source URL constants
- Define `OUTPUT_PATH` pointing to the catalog location in science-model
- Define `RECOMMENDED_ENTITY_TYPES` and `RECOMMENDED_PREDICATES` sets
- Fetch/parse the ontology programmatically (or read from a local file)
- Output a YAML file matching the `OntologyCatalog` schema:
  ```yaml
  ontology: "<name>"
  version: "<version>"
  prefix: "<prefix>"
  prefix_uri: "<uri>"
  entity_types: [...]
  predicates: [...]
  ```
- Print summary counts on completion

**Run:** `uv run scripts/extract_<ontology>_catalog.py`

**Gate:** Script exits 0, output file exists, summary shows reasonable counts.

*Skip this step if creating a hand-built catalog (no community ontology). Author
the catalog YAML directly following the schema above.*

### Step 2: Add catalog to science-model

**Create:** `science-model/src/science_model/ontologies/<ontology>/catalog.yaml`
- This is the extraction script output (or hand-authored YAML)

**Modify:** `science-model/src/science_model/ontologies/registry.yaml`
- Add entry:
  ```yaml
  - name: <ontology>
    version: "<version>"
    source_url: "<source url>"
    description: "<one-line description>"
    catalog_path: "<ontology>/catalog.yaml"
  ```

**Gate:** Verify loading works:
```python
from science_model.ontologies import load_catalogs_for_names
catalogs = load_catalogs_for_names(["<ontology>"])
assert len(catalogs) == 1
assert len(catalogs[0].entity_types) > 0
assert len(catalogs[0].predicates) > 0
```

Run: `uv run --frozen python -c '<the above>'`

### Step 3: Tests

**Modify:** `science-model/tests/test_ontologies.py`

Add tests for the new ontology:
- `test_load_<ontology>_catalog_parses_entity_types` — catalog loads, entity
  types have expected count range, spot-check 2-3 key types exist with correct
  fields
- `test_load_<ontology>_catalog_parses_predicates` — predicates load, spot-check
  2-3 key predicates
- `test_<ontology>_recommended_counts` — recommended entity types in range
  20-50, recommended predicates in range 15-35
- `test_<ontology>_curie_prefixes` — key entity types have non-empty
  `curie_prefixes` lists

**Modify:** `science-tool/tests/test_ontology_suggest.py`

Add tests for the new ontology's suggestion triggers:
- `test_suggests_<ontology>_for_curie_prefixes` — entity with a domain-specific
  CURIE triggers suggestion
- `test_suggests_<ontology>_for_kind_match` — entity with kind matching an
  ontology entity type triggers suggestion
- `test_no_suggestions_when_<ontology>_declared` — no suggestion fires when
  ontology is declared in `science.yaml`

**Gate:** `uv run --frozen pytest science-model/tests/test_ontologies.py science-tool/tests/test_ontology_suggest.py -v`

All tests pass.

### Step 4: End-to-end validation

Create a temporary test project (or use an existing one) with the new ontology
declared:

```yaml
name: test-<domain>
ontologies: [<ontology>]
knowledge_profiles:
  local: local
```

Create a few test entities using the new ontology's entity types and verify:

1. `science-tool graph build` completes without error
2. Entities with ontology-typed kinds get `profile: "<ontology>"`
3. No "unknown kind" warnings for declared ontology types
4. Suggestion mechanism fires correctly for undeclared usage (remove the
   ontology from `science.yaml` temporarily, rebuild, check output)

**Gate:** All four checks pass.

### Step 5: Update documentation

**Modify:** `references/science-yaml-schema.md`
- Update the `ontologies` field description or comments to list the new ontology
  as available

**Modify:** `commands/create-project.md` (if it references available ontologies)
- Add the new ontology to any lists of available options

**Gate:** Read modified files and verify the new ontology is mentioned correctly.

### Step 6: Run full test suite

**Run:** `uv run --frozen pytest`

**Gate:** All tests pass, no regressions.

---

## Reference: Key Files

| Purpose | Path |
|---------|------|
| Ontology Pydantic models | `science-model/src/science_model/ontologies/schema.py` |
| Ontology loading functions | `science-model/src/science_model/ontologies/__init__.py` |
| Ontology registry | `science-model/src/science_model/ontologies/registry.yaml` |
| Biology catalog (example) | `science-model/src/science_model/ontologies/biology/catalog.yaml` |
| Biology extraction script (example) | `scripts/extract_biology_catalog.py` |
| Entity source loading & profile routing | `science-tool/src/science_tool/graph/sources.py` |
| Ontology suggestion mechanism | `science-tool/src/science_tool/graph/suggest.py` |
| Graph materialization | `science-tool/src/science_tool/graph/materialize.py` |
| Ontology tests | `science-model/tests/test_ontologies.py` |
| Suggestion tests | `science-tool/tests/test_ontology_suggest.py` |
| Project manifest schema | `references/science-yaml-schema.md` |
| Design spec (biology, example) | `docs/specs/2026-03-24-ontology-consumption-design.md` |

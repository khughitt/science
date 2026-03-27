# science.yaml Schema

The project manifest. Located at the project root.

## Fields

```yaml
# Required
name: "string"              # Project name (kebab-case recommended)
created: "YYYY-MM-DD"       # Date project was created
last_modified: "YYYY-MM-DD" # Date of last significant update
summary: "string"           # 2-3 sentence project description
status: "string"            # One of: active, paused, completed, archived
profile: "string"           # One of: research, software
layout_version: 2           # Current layout version

# Required (may be empty initially)
tags:                        # Keywords for categorization
  - "string"
data_sources:                # Known data sources
  - name: "string"          # Data source name
    type: "string"          # genomic, clinical, imaging, text, other
    url: "string"           # Access URL
    access: "string"        # public, restricted, requires-application

# Optional — domain ontologies for entity types and relation predicates
ontologies:                    # Default: [] (none)
  - "string"                   # Ontology name, e.g. biolink, physics, qudt. Validated against built-in registry.

# Required for knowledge-graph-enabled projects
knowledge_profiles:
  local: "string"              # Local source directory name, e.g. local

# Optional — project aspects (composable mixins)
# Each aspect contributes additional sections, signal categories, and guidance to commands.
# See aspects/ directory for available aspects and what they provide.
aspects:                        # Default: [] (no aspects)
  - "string"                    # One of: causal-modeling, hypothesis-testing, computational-analysis, software-development
```

## Status Values

| Status | Meaning |
|---|---|
| `active` | Currently being worked on |
| `paused` | Temporarily on hold |
| `completed` | Research questions answered, project wrapped up |
| `archived` | No longer active, kept for reference |

## Example

```yaml
name: "branching-detection"
created: "2025-03-01"
last_modified: "2025-03-15"
summary: >
  Developing a unified framework for detecting branching and duplication
  processes across natural phenomena using generative models, L-systems,
  and iterated function systems.
status: "active"
profile: "research"
layout_version: 2
tags:
  - fractal-geometry
  - generative-models
  - spectral-analysis
  - genomics
data_sources:
  - name: "TCGA RNA-seq"
    type: "genomic"
    url: "https://portal.gdc.cancer.gov/"
    access: "public"
  - name: "OpenAlex concepts"
    type: "text"
    url: "https://api.openalex.org/"
    access: "public"
ontologies: [biolink]
knowledge_profiles:
  local: local
aspects:
  - causal-modeling
  - hypothesis-testing
```

## Software Project Example

```yaml
name: "cats"
created: "2026-03-18"
last_modified: "2026-03-18"
summary: >
  CLI tool for browsing, filtering, and rendering cat-related content with a
  conventional packaged Python application layout.
status: "active"
profile: "software"
layout_version: 2
tags:
  - cli
  - tooling
data_sources: []
knowledge_profiles:
  local: local
aspects:
  - software-development
```

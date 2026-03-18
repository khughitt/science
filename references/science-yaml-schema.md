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

# Required for knowledge-graph-enabled projects
knowledge_profiles:
  curated: ["string"]        # Curated graph profiles, e.g. [bio]
  local: "string"            # Local source directory name, e.g. project_specific

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
knowledge_profiles:
  curated: [bio]
  local: project_specific
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
  curated: []
  local: project_specific
aspects:
  - software-development
```

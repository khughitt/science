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

# Required (may be empty initially)
tags:                        # Keywords for categorization
  - "string"
data_sources:                # Known data sources
  - name: "string"          # Data source name
    type: "string"          # genomic, clinical, imaging, text, other
    url: "string"           # Access URL
    access: "string"        # public, restricted, requires-application

# Optional — path mappings for imported projects
# Omit entirely for standard Science layout (all defaults apply)
# Only list non-default mappings
paths:
  doc_dir: "string"          # Default: doc/
  code_dir: "string"         # Default: code/
  data_dir: "string"         # Default: data/
  models_dir: "string"       # Default: models/
  specs_dir: "string"        # Default: specs/
  papers_dir: "string"       # Default: papers/
  knowledge_dir: "string"    # Default: knowledge/
  tasks_dir: "string"        # Default: tasks/
  templates_dir: "string"    # Default: templates/
  prompts_dir: "string"      # Default: prompts/

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
aspects:
  - causal-modeling
  - hypothesis-testing
```

## Imported Project Example

```yaml
name: "natural-systems-guide"
created: "2025-12-01"
last_modified: "2026-03-09"
summary: >
  Interactive guide to natural systems models, cataloging mathematical models
  across physics, chemistry, and biology with a parameter ontology and
  interactive web demonstrations.
status: "active"
tags:
  - mathematical-models
  - parameter-ontology
  - interactive-visualization
data_sources: []
paths:
  doc_dir: docs/
  code_dir: src/
  models_dir: src/natural/registry/
aspects:
  - computational-analysis
  - software-development
```

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
```

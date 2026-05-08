# Researcher Attention Workspace Design

**Date:** 2026-05-08
**Status:** Draft for user review

## Goal

Design the first serious Science web UI around the working researcher's daily orientation problem:

> What deserves my attention, what looks promising, what is fragile, and what should I do to gain clarity?

The UI should start with a high-level, simple view and offer details on demand. It should support multiple projects from the beginning, while leaving collaborator-facing notebook/report polish as a later presentation layer over the same underlying model.

The default stance is skeptical. Interesting leads may be highlighted, but uncertainty and weak support must be just as visible as apparent promise.

## Product Shape

Use a **Split Attention Workspace** with three synchronized surfaces:

1. **Mixed Attention Graph**
   - A coarse graph of roughly 10-50 nodes.
   - Default first-open slice is `3` Mixed Attention.
   - Keyboard shortcuts switch graph composition presets:
     - `1`: Projects + Findings
     - `2`: Projects + Questions
     - `3`: Mixed Attention
   - Mixed Attention may include projects, key findings, hypotheses, questions, datasets, workflows, tasks, papers/sources, and other high-scoring entities.

2. **Findings Ledger**
   - A ranked textual view of findings and leads.
   - Default sort is Composite Attention, weighted most strongly toward importance and fragility.
   - Secondary tabs: Promising, Fragile, Recent, Actionable.
   - The ledger must distinguish "promising" from "credible"; a finding can be important and interesting while still thinly supported.

3. **Research Meaning Sidebar**
   - Opens when an entity is selected.
   - Emphasizes scientific meaning before operational details.
   - Shows title, type, project, concise summary, why it matters, current belief/evidence state, weak points, and key relationships.
   - Operational state such as files, tasks, and workflows appears lower in the sidebar or behind a secondary section.

The graph and ledger are two views over the same attention model. The graph supports spatial orientation and discovery; the ledger keeps the workspace scannable and grounded.

## Core Primitive: Finding

A **finding** is a concise, inspectable research claim with provenance. Findings may be extracted from:

- interpretation documents
- synthesis reports
- DAG edge evidence YAML
- graph propositions and observations
- task findings
- later explicit finding entities

Each finding should expose:

- concise claim text
- project and related entities
- importance score
- fragility score
- interestingness or lead value
- evidence status
- identification strength when causal
- internal data support summary
- literature and external support summary
- counterevidence or eliminated/retracted status
- provenance trail: source docs, tasks, datasets, workflows, outputs, papers
- uncertainty and caveats

## Skeptical Confidence Model

The UI must not convey confidence from salience, biological plausibility, ontology mentions, literature density, or a single strong correlation. Confidence is earned primarily by reproducible empirical work performed inside the user's projects.

Support classes:

- **Strongest support:** multiple independent internal data experiments or Snakemake workflows that were explicitly authored, run, and traced to outputs.
- **Moderate support:** one reproducible internal data workflow plus independent replication, sensitivity analysis, or strong methodological fit.
- **Weak support:** literature support, ontology support, prior plausibility, external reports, or untested synthesis.
- **Untrustworthy by default:** no internal data support, or only one internal experiment without replication or sensitivity checks.
- **Still fragile:** any claim whose apparent support comes from one correlation, one dataset family, one workflow, or one modeling choice.

The UI may highlight interesting leads, but it must pair that highlight with visible uncertainty. The purpose is not to suppress speculation; it is to help choose future work that can gain clarity one way or the other.

Concrete UI implications:

- The ledger separates **Promising** from **Credible**.
- The sidebar shows **Internal data support** before literature or ontology support.
- Single-experiment findings get an explicit "single internal test" caveat.
- Literature-only and ontology-only items may rank as interesting, but should not look confident.
- The graph evidence lens favors workflow-backed internal support.
- Fragility is a first-class signal, not a hidden penalty.

## Evidence Semantics

Preserve the Science proposition/evidence model:

- propositions remain uncertain
- evidence updates belief
- support and dispute are both first-class
- hypotheses are bundles of uncertain propositions
- confidence, uncertainty, contestation, and fragility are derived interpretations of the record

For DAG-derived evidence, preserve the two-axis MM30 convention rather than collapsing it into one confidence score:

- `edge_status`: `supported`, `tentative`, `structural`, `unknown`, `eliminated`
- `identification`: `interventional`, `longitudinal`, `observational`, `structural`, `none`

The UI should be able to say, for example, "strongly replicated but only observational" without treating that as equivalent to causal identification.

## Graph Encoding

Use a declarative visual encoding model inspired by ggplot2 and Cytoscape, exposed through restrained controls.

Default mapping:

```yaml
nodes:
  color: semantic_domain
  shape: entity_type
  size: attention_importance
  ring_or_glow: activity
  texture: provenance_class
edges:
  color: evidence_status
  width: load_bearingness
  style: uncertainty_or_eliminated_state
  arrow_or_badge: identification_strength
```

Named lenses should be the primary UI:

- Semantic
- Evidence
- Fragile
- Recent
- Projects
- Workflows

A compact Mapping panel may allow one-channel-at-a-time overrides for color, size, shape, edge color, and edge width. Mapping tweaks persist automatically across sessions. Project-authored named graph views are deferred.

The default graph should be deterministic, not a random sample on each load. Use a stable attention slice, then provide explicit discovery modes later such as Random Sample or Shuffle.

## Attention Scoring

The attention model should keep several signals separate, even if the default sort combines them:

- importance
- fragility
- interestingness
- recency
- actionability
- centrality
- load-bearingness
- internal support strength
- external support strength
- unresolved uncertainty
- blocked or high-priority task pressure

Default Composite Attention should emphasize importance and fragility most strongly, with recency and actionability still visible. "Interesting" should increase attention, not confidence.

## Interaction Model

Graph interaction:

- Hover: lightweight card with title, type, status, and strongest signal.
- Click: select entity, ease camera toward it, emphasize first-order neighborhood, and open the sidebar.
- Click related entity in sidebar: refocus graph and update sidebar.
- `Escape` or Back: return through focus history.
- `Enter` or double click: open the full detail/provenance view.
- `1`, `2`, `3`: switch graph composition preset.

Implementation direction: use `r3f-forcegraph` unless a prototype exposes a blocker. It fits the React Three Fiber composition model and supports custom nodes, links, hover/click callbacks, and camera/scene composition needed for a polished spatial entity browser.

## Architecture And Data Flow

Remain filesystem-first. Science project files stay the source of truth; the web app derives read models from them.

Recommended data flow:

1. **Project scan** reads configured project roots: `science.yaml`, docs/frontmatter, tasks, graph files, DAG evidence YAML, synthesis reports.
2. **Attention analysis** derives candidate entities and scores.
3. **Finding extraction** normalizes findings from existing artifacts.
4. **Graph slice builder** chooses the 10-50 node view based on the active slice preset and attention scores.
5. **Visual encoding layer** maps entity/edge fields into style channels using defaults plus persisted user overrides.
6. **Frontend workspace** renders graph, ledger, and sidebar from the same read model.

V1 should be read-only except for local UI preferences. No graph edits, no finding edits, no saved project views, and no write-back of visual mappings to Science project files.

## Error And Degraded Behavior

- Missing graph: show ledger/sidebar from file-derived findings and explain that graph data is unavailable.
- Missing evidence fields: keep the finding visible and mark evidence status or identification as unavailable.
- Broken refs: surface as quality issues; do not silently drop them from provenance.
- Sparse project: show fewer than 10 graph nodes rather than padding.
- Huge project: cap default slice at 50 nodes and explain the slice basis.
- Unknown entity type: render with a default shape and expose the raw type.
- Literature-only or ontology-only support: mark as weak support even if the item is interesting.

## Deferred Work

### Collaborator Notebook View

The collaborator-facing lab notebook/report view should reuse findings and provenance, but present them as a concise narrative:

- summary
- small number of key findings
- expandable audit trail per finding
- workflow/provenance graph
- uncertainty and caveats

This is a presentation mode over the same model, not a separate product.

### Entity-Specific Visual Representations

Track a later extension point allowing entity types to provide richer visual profiles:

- genes: sequence or locus visualization
- proteins: AlphaFold or structure visualization
- inquiries: DAG figure
- datasets: schema, coverage, or sample panel
- workflows: mini workflow DAG
- papers/sources: citation/source card

Do not build this into v1.

### Saved Graph Views

Named, project-authored graph views such as `views/fragile-findings.yaml` are deferred. V1 only persists local user preferences automatically.

## Testing And Acceptance

Testing should cover:

- deterministic attention scoring and slice selection
- finding extraction from DAG edge YAML, tasks, synthesis reports, and graph propositions
- skeptical confidence classification from internal workflow support versus literature-only support
- visual mapping defaults and preference persistence
- keyboard slice switching
- node click/refocus/sidebar behavior
- missing graph, sparse project, broken refs, unknown entity type
- two-axis evidence rendering and ledger display

Acceptance criteria for v1:

- First open shows Split Attention Workspace with `3` Mixed Attention.
- The graph displays a deterministic 10-50 node attention slice when enough entities exist.
- The findings ledger defaults to Composite Attention and visibly separates promise from credibility.
- `1`, `2`, and `3` switch graph composition presets.
- Clicking a node zooms/refocuses and opens a research-meaning sidebar.
- Ledger and graph share the same attention model.
- Evidence status and identification strength remain distinct.
- Internal workflow/data support is weighted above literature and ontology support for confidence.
- Literature-only and single-experiment findings are visibly fragile or weakly supported.
- UI preferences persist automatically, but no project files are modified.

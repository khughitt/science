# Researcher Attention Workspace Design

**Date:** 2026-05-08
**Status:** Draft for user review

## Goal

Design the first serious Science web UI around the working researcher's daily orientation problem:

> What deserves my attention, what looks promising, what is fragile, and what should I do to gain clarity?

The UI should start with a high-level, simple view and offer details on demand. It should support multiple projects from the beginning, while leaving collaborator-facing notebook/report polish as a later presentation layer over the same underlying model.

The default stance is skeptical. Interesting leads may be highlighted, but uncertainty and weak support must be just as visible as apparent promise.

## Multi-Project Model

V1 starts in **All Projects** scope. The workspace reads the configured project roots from the web app config and includes every reachable project in the first-open attention model. If only one project is configured, the same UI operates as a single-project workspace.

Project scope is explicit UI state:

- **All Projects**: default first-open scope; includes all configured and reachable projects.
- **One Project**: focuses the attention model on one project.
- **Selected Set**: deferred as an editable scope, but URL state may represent a selected set once the backend can accept it.

Attention scores are normalized in two stages:

1. **Per-project normalization:** each signal is normalized within its own project first. This lets a small project's strongest finding compete with a large project's strongest finding.
2. **Global merge normalization:** after per-project scoring, scores are merged into one candidate pool and lightly adjusted by cross-project centrality and peer links.

Do not rank raw counts globally across projects. A large project with many tasks, findings, or papers should not drown out a smaller project's important fragile result.

Cross-project relationships use the project-peers/addressing model:

- Cross-project refs use namespace-first entity refs such as `mm30:finding:f012` or `cbioportal:dataset:mutation-cohort`.
- Peer links, shared datasets, shared papers/sources, and explicit cross-project refs can render as cross-project edges.
- Cross-project edges are visually distinct with a subtle dashed or bundled style and must show both owning projects in the sidebar/tooltip.
- Missing or unresolved peer paths produce visible quality issues and do not silently remove authored refs.

Composition presets operate over the current project scope:

- In All Projects, presets mix entities across projects after per-project normalization.
- In One Project, presets include only that project.
- In a future Selected Set, presets include only the selected projects.

## Product Shape

Use a **Split Attention Workspace** with three synchronized surfaces:

1. **Mixed Attention Graph**
   - A coarse graph of roughly 10-50 nodes.
   - Default first-open slice is `3` Mixed Attention.
   - Keyboard shortcuts switch graph composition presets:
     - `1`: Findings
     - `2`: Hypotheses
     - `3`: Mixed Attention
     - `4`: Inquiries / DAGs
   - Mixed Attention may include projects, key findings, hypotheses, questions, inquiries, DAGs, datasets, workflows, tasks, papers/sources, and other high-scoring entities.

2. **Findings Ledger**
   - A ranked textual view of findings and leads.
   - Default sort is Composite Attention, weighted most strongly toward importance and fragility.
   - Secondary tabs: Promising, Credible, Fragile, Recent, Actionable, Ruled Out.
   - The ledger must distinguish "promising" from "credible"; a finding can be important and interesting while still thinly supported.
   - Eliminated, superseded, falsified, or otherwise ruled-out findings remain inspectable in the Ruled Out tab and are tombstoned rather than hidden.

3. **Research Meaning Sidebar**
   - Opens when an entity is selected.
   - Emphasizes scientific meaning before operational details.
   - Shows title, stable ID, type, project, concise summary, why it matters, current belief/evidence state, weak points, and key relationships.
   - Operational state such as files, tasks, and workflows appears lower in the sidebar or behind a secondary section.
   - Key relationships are capped to the top 8 by load-bearingness, attention, and direct provenance relevance. Each row shows relation type, target type, target project, and why the relationship is shown.

The graph and ledger are two views over the same attention model. The graph supports spatial orientation and discovery; the ledger keeps the workspace scannable and grounded.

## Finding Data Model

A **finding** is a concise, inspectable research claim with provenance. It should reuse the existing Science proposition/evidence model rather than create a parallel claim universe.

V1 represents findings as derived read-model records with stable IDs. When a source artifact already has a canonical finding entity, preserve that entity ID. Otherwise derive a stable synthetic ID from the project ID, source kind, source path/entity ref, source-local edge or section ID, and a normalized proposition ref when available.

Canonical ID form:

```text
<project-id>:finding:<slug>
```

Synthetic ID form:

```text
<project-id>:finding:auto:<source-kind>:<stable-hash>
```

The hash must be deterministic and must not include volatile fields such as build timestamp, local absolute path prefixes, or score values.

V1 finding schema:

| Field | Meaning |
|---|---|
| `id` | Stable canonical or synthetic finding ID. |
| `project_id` | Owning project ID. |
| `claim_text` | Concise human-readable claim. |
| `proposition_refs` | Existing proposition refs when available. Prefer these over free-text identity. |
| `source_refs` | Source docs, graph nodes, DAG edge records, tasks, papers, workflows, datasets. |
| `primary_source` | The source used for default deep-linking. |
| `related_entities` | Typed refs for hypotheses, questions, inquiries, datasets, workflows, tasks, papers, and domain entities. |
| `evidence_status` | Supported/tentative/structural/unknown/eliminated/etc. |
| `identification_strength` | Interventional/longitudinal/observational/structural/none/unavailable. |
| `support_class` | Strongest/moderate/weak/untrustworthy/still-fragile derived from the skeptical confidence model. |
| `support_breakdown` | Internal workflow support, external/literature support, ontology support, counterevidence. |
| `scores` | Importance, fragility, interestingness, recency, actionability, credibility, composite attention. |
| `score_reasons` | Short auditable reasons for each non-zero score contribution. |
| `supersession` | Supersedes/superseded-by/eliminated-by refs when present. |
| `freshness` | Fresh/needs-review/stale/unavailable. |

Findings are graph nodes when they rank into the active slice or are explicitly selected. They are always ledger rows if they pass the current ledger filter. This avoids forcing every ledger item into the graph while still allowing findings to become first-class spatial entities.

Deduplication rule:

- Prefer shared `proposition_refs` as the identity key.
- If no proposition exists, use normalized claim text plus project ID plus core related entities.
- Collapse duplicate mentions into one finding when they assert the same proposition in the same project.
- Merge provenance from interpretation docs, synthesis reports, DAG edge YAML, graph propositions, and task findings into the deduplicated finding.
- Keep separate findings when scopes differ materially, when evidence directions conflict, or when one source explicitly supersedes/eliminates the other.

The sidebar must show merged provenance clearly so deduplication does not hide source disagreements.

## Skeptical Confidence Model

The UI must not convey confidence from salience, biological plausibility, ontology mentions, literature density, or a single strong correlation. Confidence is earned primarily by reproducible empirical work performed inside the user's projects.

Support classes:

- **Strongest support:** multiple independent internal data experiments or Snakemake workflows that were explicitly authored, run, and traced to outputs.
- **Moderate support:** one reproducible internal data workflow plus independent replication, sensitivity analysis, or strong methodological fit.
- **Weak support:** literature support, ontology support, prior plausibility, external reports, or untested synthesis.
- **Untrustworthy by default:** no internal data support, or only one internal experiment without replication or sensitivity checks.
- **Still fragile:** any claim whose apparent support comes from one correlation, one dataset family, one workflow, or one modeling choice.

Stale internal workflows downgrade support. A finding backed by a workflow whose inputs, code, parameters, or declared source refs changed after its last successful run cannot be stronger than weak support until it is rerun or reviewed.

The UI may highlight interesting leads, but it must pair that highlight with visible uncertainty. The purpose is not to suppress speculation; it is to help choose future work that can gain clarity one way or the other.

Concrete UI implications:

- The ledger separates **Promising** from **Credible**.
- The sidebar shows **Internal data support** before literature or ontology support.
- Single-experiment findings get an explicit "single internal test" caveat.
- Literature-only and ontology-only items may rank as interesting, but should not look confident.
- The graph evidence lens favors workflow-backed internal support.
- Fragility is a first-class signal, not a hidden penalty.
- A score-breakdown inspector explains why any item ranks high.

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

Rendering rules:

- `identification: none` renders as an explicit "not identified" badge, not as a missing badge.
- Missing identification renders as "unavailable."
- `edge_status: unknown` means the status was classified as unknown or untested.
- Missing evidence status renders as "unclassified."
- Eliminated evidence remains visible with a tombstoned ledger treatment and muted/dotted graph styling.

Existing audit signals feed fragility:

- DAG audit drift increases fragility for affected edges/findings and can mark them needs-review.
- Bias-audit findings increase fragility for affected hypotheses/findings.
- Pre-registration awaiting-results state contributes to actionability but is distinct from generic task pressure.
- Needs-review/stale freshness state increases fragility and actionability without changing the underlying evidence status.

## Graph Encoding

Use a declarative visual encoding model inspired by ggplot2 and Cytoscape, exposed through restrained controls.

Default mapping:

```yaml
nodes:
  color: semantic_domain
  shape: entity_type
  size: attention_importance
  ring_or_glow: activity_or_changed_since_last_view
  border: provenance_class
edges:
  color: evidence_status
  width: load_bearingness
  style: uncertainty_or_eliminated_state
  arrow_or_badge: identification_strength
```

Use border style, ring style, or small icons before texture for provenance because texture is hard to read at small node sizes.

Named lenses should be the primary UI:

- Semantic
- Evidence
- Fragile
- Recent
- Projects
- Workflows

A compact Mapping panel may allow one-channel-at-a-time overrides for color, size, shape, edge color, and edge width. Mapping tweaks persist automatically across sessions. Project-authored named graph views are deferred.

The default graph should be deterministic in membership and stable enough in layout for repeated use:

- Node and edge membership are deterministic for a given read-model snapshot and UI state.
- V1 default rendering is 2D for legibility at 10-50 nodes.
- 3D/r3f-forcegraph remains the preferred interactive/polished direction, but it must be prototyped before becoming the default.
- If a force-directed layout is used in V1, seed the simulation or persist snapshot positions in the read model. If neither is possible in the first prototype, document layout nondeterminism as a known limitation while keeping node membership deterministic.

Discovery modes such as Random Sample or Shuffle are deferred and must be explicit user actions, not the first-open default.

Accessibility requirements:

- Color palettes must distinguish semantic/evidence states under common color-vision deficiencies.
- Evidence status and entity type need non-color secondary cues such as icons, shape, line style, label chips, or badge letters.
- The sidebar and ledger must expose every visual encoding as text.

## Attention Scoring

The attention model keeps signals separate, even when the default sort combines them. Every score is normalized to `0.0-1.0` per project before global merge. Missing values default to `0.0` except when noted. Tie-breaking is deterministic: higher composite score, higher fragility, higher importance, more recent update, project ID, entity ID.

V1 signal reference:

| Signal | Definition | Source | Normalization | Default composite weight |
|---|---|---|---|---:|
| `importance` | How central/load-bearing the item is to project meaning. | Graph degree, explicit priority, linked hypotheses/questions, synthesis prominence. | Project-local percentile with log scaling for degree-like counts. | 0.22 |
| `fragility` | How easily current belief could change. | Sparse internal support, contested evidence, single workflow, stale workflow, DAG drift, bias-audit issue, needs-review. | Rule-derived score capped at 1.0. | 0.22 |
| `interestingness` | Lead value independent of confidence. | Large effect, surprising relation, cross-project bridge, unresolved high-value question, ontology/literature novelty. | Project-local percentile; never contributes to confidence. | 0.12 |
| `recency` | How recently the item or upstream evidence changed. | `updated`, source mtime, workflow-run date, graph freshness upstream change. | Exponential decay by age; unavailable is 0.0. | 0.10 |
| `actionability` | How directly the item implies next work. | Ready tasks, blocked tasks, pre-registration awaiting results, validation/audit flags. | Rule-derived score from task/readiness state. | 0.14 |
| `centrality` | Graph-theoretic centrality within the project or selected scope. | Project graph / read-model graph. | Project-local percentile. | 0.08 |
| `load_bearingness` | Number/weight of important downstream findings or decisions depending on the item. | `bears_on`, provenance, DAG dependencies, task blockers. | Project-local percentile with log scaling. | 0.08 |
| `internal_support_strength` | Credible support from internal reproducible workflows/data experiments. | Workflow runs, data packages, observations, DAG data support. | Rule-derived support class mapped to score. | Confidence only; not raw attention. |
| `external_support_strength` | Literature, ontology, and external source support. | Paper/source refs, ontology matches, lit support. | Project-local count/quality percentile. | Confidence only; small boost to interestingness. |
| `unresolved_uncertainty` | Open uncertainty not already captured by fragility. | Unknown/tentative statuses, open questions, missing evidence fields. | Rule-derived score capped at 1.0. | 0.04 |
| `task_pressure` | Operational pressure from high-priority, blocked, or ready tasks. | Task status, priority, blockers, related refs. | Rule-derived score capped at 1.0. | Included in actionability. |

Composite Attention v1:

```text
attention =
  0.22 * importance +
  0.22 * fragility +
  0.12 * interestingness +
  0.10 * recency +
  0.14 * actionability +
  0.08 * centrality +
  0.08 * load_bearingness +
  0.04 * unresolved_uncertainty
```

The weights are defaults, not a scientific claim. They should be visible in a score-breakdown inspector and remain easy to tune in implementation tests.

Composite score transparency:

- Ledger rows expose top score reasons on hover or expand.
- The sidebar has a Score Breakdown section with raw signal values, normalized values, and source evidence.
- Any item that ranks high from interestingness but low from credibility must visibly say so.
- The graph slice explanation states which scope, preset, snapshot, and score basis selected the current nodes.

## Interaction Model

Graph interaction:

- Hover: lightweight card with title, type, project, status, and strongest signal.
- Click: select entity, ease camera toward it, emphasize first-order neighborhood, and open the sidebar.
- Click related entity in sidebar: refocus graph and update sidebar.
- `Escape`: clear focus or step back through focus history.
- Browser Back: navigates URL history, which may also restore previous focus state.
- `Enter` or double click: open the full detail/provenance view.
- `1`, `2`, `3`, `4`: switch graph composition preset.
- `/` or search affordance: deferred if not built in V1, but the design should reserve a jump-to-entity command because large projects need it.

Implementation direction: prototype r3f-forcegraph for the polished spatial browser, but keep V1 default 2D unless the prototype proves 3D is equally legible and performant for 10-50 nodes.

## State And Persistence

URL state should encode sharable/navigation-relevant state:

- project scope (`all`, one project ID, or future selected set)
- graph preset (`1`/`2`/`3`/`4`)
- active lens
- selected entity/finding ID
- ledger tab/sort
- optional search query

Browser history should work with graph focus history. Selecting an entity updates the URL; Back restores the previous selected entity or preset.

Local user preferences persist in browser storage:

- mapping overrides
- last-used lens
- ledger tab/sort
- sidebar section expansion
- graph display options such as labels on/off

Use `localStorage` for small JSON preferences in V1. Move to IndexedDB only if preferences grow into large layout snapshots or cached read models. Preferences are single-browser and single-user; cross-device sync is out of scope. The default startup graph preset remains Mixed Attention unless a later settings UI explicitly changes that default.

UI preferences must not modify Science project files.

## Architecture And Data Flow

Remain filesystem-first. Science project files stay the source of truth; the web app derives read models from them.

Recommended data flow:

1. **Project scan** reads configured project roots: `science.yaml`, peers, docs/frontmatter, tasks, graph files, DAG evidence YAML, synthesis reports.
2. **Finding extraction** normalizes findings from existing artifacts and deduplicates by proposition/source identity.
3. **Attention analysis** derives candidate entities and scores with per-project normalization.
4. **Graph slice builder** chooses the 10-50 node view based on the active scope, preset, snapshot, and attention scores.
5. **Visual encoding layer** maps entity/edge fields into style channels using defaults plus persisted user overrides.
6. **Frontend workspace** renders graph, ledger, and sidebar from the same read model.

V1 should be read-only except for local UI preferences. No graph edits, no finding edits, no saved project views, and no write-back of visual mappings to Science project files.

### Build And Freshness

The web app builds a read-model snapshot at startup or first page load, then refreshes when configured project files change. Manual refresh is available from the UI.

Build contract:

- Each read-model snapshot has a `snapshot_id`, `built_at`, included project IDs, source project HEAD/mtime summary, and schema version.
- The UI shows `built_at` unobtrusively and exposes snapshot details in a status popover.
- File-watch refresh may debounce rapid file changes and rebuild affected project analyses first, then the merged attention model.
- If a rebuild fails, keep the last successful snapshot visible with a stale/error banner.
- If graph files are stale or missing, show ledger/sidebar data from source files and mark graph-derived signals unavailable.

Performance target for V1:

- Cold load for a typical small/medium configured workspace should aim for under 5 seconds before the first useful ledger/graph render.
- Re-slicing an existing snapshot should aim for under 250 ms.
- If full DAG/graph/evidence parsing exceeds the cold-load budget, the implementation should render a partial snapshot first and progressively fill expensive evidence fields with explicit loading/stale markers.

Read-model versioning matters for trust. Any sidebar or score-breakdown view should show the snapshot ID or build timestamp so the user can tell whether the UI is describing current files.

## Error And Degraded Behavior

- Fresh project with few artifacts: show an empty-state path that points to creating hypotheses/questions/findings or building the graph.
- Missing graph: show ledger/sidebar from file-derived findings and explain that graph data is unavailable.
- Graph not yet built: show the command or action needed to build it.
- Missing evidence fields: keep the finding visible and mark evidence status or identification as unavailable.
- Broken refs: surface as quality issues; do not silently drop them from provenance.
- Sparse project: show fewer than 10 graph nodes rather than padding.
- Huge project: cap default slice at 50 nodes and explain the slice basis.
- Unknown entity type: render with a default shape and expose the raw type.
- Literature-only or ontology-only support: mark as weak support even if the item is interesting.
- Missing peer path: keep authored cross-project refs visible as unresolved peer issues.

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

### Export And Citation

Deep links to findings are in V1. Structured export, JSON citation bundles, and source/BibTeX-style export are useful but deferred unless they are cheap once the finding read model exists.

## Testing And Acceptance

Testing should cover:

- multi-project per-project normalization and global merge behavior
- cross-project edge rendering from project-peers refs and shared sources
- stable finding IDs and deduplication across DAG YAML, synthesis reports, graph propositions, and tasks
- deterministic attention scoring and slice selection with score-breakdown reasons
- skeptical confidence classification from internal workflow support versus literature-only support
- stale workflow downgrading of support class
- visual mapping defaults and preference persistence
- URL state for scope, preset, lens, selected entity, and ledger tab
- keyboard slice switching
- node click/refocus/sidebar behavior
- missing graph, sparse project, broken refs, unknown entity type, missing peer path
- two-axis evidence rendering and ledger display, including `identification: none`, missing identification, `edge_status: unknown`, and missing status
- ruled-out/superseded/eliminated findings remain inspectable

Acceptance criteria for v1:

- First open shows All Projects scope with Split Attention Workspace and `3` Mixed Attention.
- The graph displays a deterministic 10-50 node attention slice when enough entities exist.
- The findings ledger defaults to Composite Attention and visibly separates promise from credibility.
- `1`, `2`, `3`, and `4` switch graph composition presets.
- Clicking a node zooms/refocuses and opens a research-meaning sidebar.
- Ledger and graph share the same attention model.
- Evidence status and identification strength remain distinct.
- Internal workflow/data support is weighted above literature and ontology support for confidence.
- Literature-only and single-experiment findings are visibly fragile or weakly supported.
- A project with internally reproduced workflow-backed findings and literature-only findings ranks the internal workflow-backed findings higher in Credible, while literature-only leads can still rank in Promising.
- Stale internal workflows downgrade support until rerun or reviewed.
- Score breakdowns explain why high-ranked items are high-ranked.
- URL state supports bookmarking the current scope, preset, lens, selected entity, and ledger tab.
- UI preferences persist automatically in browser-local storage, but no project files are modified.

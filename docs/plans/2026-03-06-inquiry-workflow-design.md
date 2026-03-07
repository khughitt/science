# Evidence-Driven Modeling Workflow: Design

- **Date:** 2026-03-06
- **Status:** draft
- **Scope:** Inquiry abstraction, 4 new commands, ontology extensions, graph store changes, validation, templates
- **Derived from:** `docs/plan.md` (Phase 4), seq-feats exemplar (`~/d/seq-feats/doc/plans/2026-03-06-pipeline-architecture-design.md`)
- **Depends on:** Phase 3 graph infrastructure (complete), knowledge-graph skill, `science-tool` CLI

---

## 1. Problem

Science projects need to go from research questions and hypotheses to reproducible computational workflows. Today this transition is ad-hoc: a researcher writes prose specifications, then manually translates them into code, configs, and pipeline DAGs. The translation loses provenance — why a parameter has a particular value, what evidence supports a modeling assumption, which data sources feed which analyses.

The seq-feats project demonstrates what this looks like done well: an `AnnotatedParam` config system where every parameter carries its source, references, and empirical distribution. But this was built bespoke. Science should provide a generalized, problem-agnostic workflow that makes evidence-driven pipeline design the default path.

## 2. Core Abstraction: Inquiry

An **inquiry** is a named subgraph in the knowledge graph that represents a self-contained investigation — connecting data and observations to a question or hypothesis through variables, assumptions, and transformations.

### 2.1 Graph Representation

An inquiry is a TriG named graph at `:inquiry/<slug>`:

```turtle
:inquiry/signal-peptide-geometry {
  # The inquiry node itself
  inquiry:signal_peptide_geometry a sci:Inquiry ;
    sci:target hypothesis:h03 ;
    sci:inquiryStatus "sketch" ;
    dcterms:created "2026-03-06" ;
    rdfs:label "Signal peptide embedding geometry" ;
    rdfs:comment "Test whether SP embeddings occupy a distinct geometric region" .

  # Boundary-in: givens (data, observations, prior knowledge)
  concept:uniprot_reviewed_sps sci:boundaryRole sci:BoundaryIn .
  concept:esm2_650m sci:boundaryRole sci:BoundaryIn .

  # Boundary-out: produces (test results, predictions, artifacts)
  concept:sp_embedding_distances sci:boundaryRole sci:BoundaryOut .
  concept:t1_control_comparison sci:boundaryRole sci:BoundaryOut .

  # Interior nodes (no boundary role — variables, transformations, assumptions)
  # These are regular graph entities that happen to live in this inquiry subgraph

  # Edges within the inquiry
  concept:uniprot_reviewed_sps sci:feedsInto concept:sp_sequences .
  concept:sp_sequences sci:feedsInto concept:sp_embeddings .
  concept:esm2_650m sci:feedsInto concept:sp_embeddings .
  concept:sp_embeddings sci:feedsInto concept:sp_embedding_distances .
  concept:sp_embedding_distances sci:feedsInto concept:t1_control_comparison .

  # Assumptions
  concept:mean_pooling_sufficient a sci:Assumption ;
    rdfs:label "Mean pooling captures SP-relevant information" ;
    prov:wasDerivedFrom paper:doi_10_1101_2022_07_20_500902 .
  concept:sp_embeddings sci:assumes concept:mean_pooling_sufficient .
}
```

### 2.2 Key Properties

- **Composability.** Nodes can appear in multiple inquiries with different boundary roles. A dataset node might be `BoundaryIn` for one inquiry and `BoundaryOut` for another. The boundary classification is per-inquiry (it lives in the inquiry's named graph), not intrinsic to the node.

- **Shared entities.** Inquiry nodes (concepts, papers, claims) are the *same* entities as in `:graph/knowledge`. Adding a concept to an inquiry doesn't duplicate it — the inquiry graph contains edges and boundary roles that reference entities whose definitions live in the knowledge layer. This means `/science:update-graph` and `/science:create-graph` naturally see inquiry-referenced entities.

- **Lifecycle.** An inquiry progresses through statuses:
  - `sketch` — rough shape, untyped edges, missing provenance OK
  - `specified` — every edge typed, every variable defined, provenance complete
  - `planned` — computational steps added, implementation plan generated
  - `in-progress` — execution underway
  - `complete` — results produced and validated

- **Unknowns are first-class.** `sci:Unknown` nodes represent "something affects this but I don't know what." These are explicit targets for the specify step — they must be resolved or justified before an inquiry can leave sketch status.

### 2.3 Boundary Nodes

The boundary abstraction is the key design element:

| Role | Meaning | Examples |
|---|---|---|
| `sci:BoundaryIn` | Given/observable — data, measurements, prior knowledge the inquiry takes as input | Datasets, reference databases, published measurements, known facts |
| `sci:BoundaryOut` | Produces — results, predictions, artifacts the inquiry generates | Statistical test results, predictions, generated datasets, visualizations |
| *(no role)* | Interior — latent variables, transformations, assumptions, intermediate quantities | Model parameters, computational steps, modeling assumptions |

**Validation rules for boundaries:**
- Every `BoundaryIn` node should reference a real data source (dataset, paper, or existing graph entity with provenance)
- Every `BoundaryOut` node should be reachable from at least one `BoundaryIn` via directed edges
- Every interior node should have at least one incoming and one outgoing edge within the inquiry
- `sci:Unknown` nodes cannot be `BoundaryIn` (you can't take unknown data as input)

### 2.4 Relationship to Existing Graph Layers

| Existing layer | Inquiry interaction |
|---|---|
| `:graph/knowledge` | Inquiry references entities defined here; new entities created during sketch/specify are added here too |
| `:graph/causal` | Causal edges (`scic:causes`, `scic:confounds`) can appear within inquiries; inquiry edges like `sci:feedsInto` express computational/data flow, not causation |
| `:graph/provenance` | Provenance for inquiry entities (claims, hypotheses, assumptions) lives here as usual |
| `:graph/datasets` | Dataset measurement links (`sci:measuredBy`) apply to inquiry boundary-in nodes |

New inquiry-specific content lives in `:inquiry/<slug>` named graphs. This keeps the separation clean: the knowledge layer defines *what things are*; inquiry layers define *how they connect for a specific investigation*.

---

## 3. Command Set

Four commands that compose into a workflow:

```
/science:sketch-model  →  /science:specify-model  →  /science:plan-pipeline  →  /science:review-pipeline
     (divergent)              (convergent)              (operational)              (quality gate)
```

Each command can also be used standalone. `specify-model` can start fresh (without a prior sketch). `review-pipeline` can review any specified inquiry, even without a formal plan.

### 3.1 `/science:sketch-model`

**Purpose:** Get the shape of the problem down quickly. Divergent thinking. Missing provenance is fine.

**Trigger phrases:** "I want to model...", "what variables matter for...", "how would I test...", "sketch out..."

**Workflow:**

1. **Read context:** research question, existing hypotheses, existing graph (if any), existing inquiries
2. **Interactive conversation** (adaptive, not rigid):
   - "What are you trying to test or answer?" → identify target hypothesis/question
   - "What variables matter? What can you observe vs. what's latent?"
   - "What do you think affects what?" (rough relationships OK)
   - "What data do you have or could get?"
   - "What are you unsure about?" → create `sci:Unknown` nodes
3. **Create inquiry subgraph:**
   - Initialize inquiry named graph (`:inquiry/<slug>`)
   - Add inquiry node with target, status=sketch, label, description
   - Add nodes for each variable, data source, and unknown
   - Add edges for stated relationships (loosely typed — `skos:related` and `sci:feedsInto` are fine)
   - Classify boundary nodes (in/out)
   - Ensure all entities also exist in `:graph/knowledge` (add if missing)
4. **Render summary:**
   - Generate visualization: `graph viz --graph :inquiry/<slug>`
   - Write human-readable summary to `doc/inquiries/<slug>.md`
5. **Stamp and validate:**
   - `graph stamp-revision`
   - `graph validate`

**What's explicitly allowed to be missing in a sketch:**
- Edge provenance (no `--source` required)
- Parameter values
- Formal variable types beyond `sci:Concept`
- Confounder analysis
- Data source specifics (a node labeled "some protein database" is fine)

**Sketch-specific:** `sci:Unknown` nodes are encouraged. They represent gaps in understanding and become explicit targets for the specify step.

### 3.2 `/science:specify-model`

**Purpose:** Add rigor. Every node and edge gets evidence. Convergent thinking.

**Trigger phrases:** "specify the model", "formalize...", "add evidence to...", "make this rigorous"

**Workflow:**

1. **Load inquiry:**
   - If `$ARGUMENTS` names an existing inquiry slug → load it, identify gaps
   - If no existing inquiry → run sketch inline first, then specify
2. **For each node, ensure:**
   - Formal type (`--type biolink:Gene`, `sci:Variable`, etc.)
   - Definition (`--definition`)
   - Observable vs. latent status (property: `sci:observability` = `observed` | `latent` | `computed`)
   - Source/provenance (`--source`)
3. **For each edge, ensure:**
   - Typed predicate from the predicate registry (not `skos:related` unless genuinely associative)
   - Evidence (`--source` on claims that justify the edge)
   - Direction justification (why A→B not B→A? — captured as a claim or note)
4. **For parameter-bearing nodes, add `AnnotatedParam` metadata:**
   - Value, source type (`literature` | `empirical` | `design_decision` | `convention` | `data_derived`)
   - References (BibTeX keys or doc paths)
   - Note explaining the choice
   - Optional empirical distribution
   - Stored as structured properties on the node: `sci:paramValue`, `sci:paramSource`, `sci:paramRef`, `sci:paramNote`
5. **Confounder check:**
   - For each causal or directional edge: "What else could explain this? What's missing?"
   - Add `scic:confounds` edges for identified confounders
6. **Resolve unknowns:**
   - Every `sci:Unknown` node must be either: resolved (replaced with a real entity), justified (documented why it remains unknown, with a plan to resolve), or removed
7. **Update inquiry status** to `specified`
8. **Update `doc/inquiries/<slug>.md`** with full specification
9. **Validate:**
   - Boundary reachability (every BoundaryOut reachable from some BoundaryIn)
   - Provenance completeness (every claim, hypothesis, assumption has source)
   - No orphaned interior nodes
   - No remaining unjustified `sci:Unknown` nodes

### 3.3 `/science:plan-pipeline`

**Purpose:** From a specified model, generate a concrete computational plan with tool-specific details.

**Trigger phrases:** "plan the pipeline", "how do I implement this", "make this computational"

**Workflow:**

1. **Load specified inquiry** (must be status=`specified`; warn if sketch)
2. **Identify computational requirements** from the inquiry subgraph:
   - Which `BoundaryIn` nodes need data acquisition/preprocessing?
   - Which interior edges imply transformations?
   - Which `BoundaryOut` nodes need specific output formats?
3. **Add computational nodes** to the inquiry subgraph:
   - `sci:Transformation` nodes for each processing step
   - `sci:feedsInto` edges connecting them
   - Properties: tool/method, input format, output format, parameters (as `AnnotatedParam`)
   - Validation criteria: `sci:validatedBy` edges to `sci:ValidationCheck` nodes
4. **Generate implementation plan** document:
   - Save to `doc/plans/YYYY-MM-DD-<slug>-pipeline-plan.md`
   - Follow the standard plan format (header, tasks, TDD steps, commits)
   - Reference tool-specific skills where applicable (`skills/pipelines/snakemake.md`, `skills/pipelines/marimo.md`)
5. **Optionally generate scaffold files:**
   - Config YAML with `AnnotatedParam` structure
   - Test stubs
   - Directory structure
6. **Update inquiry status** to `planned`

**This command bridges the gap between the evidence-driven model and implementation.** The inquiry subgraph gains computational nodes but retains its evidence provenance — every transformation node connects back through the inquiry to the data and assumptions that justify it.

### 3.4 `/science:review-pipeline`

**Purpose:** Systematic review against a rubric before implementation begins.

**Trigger phrases:** "review the pipeline", "check my plan", "audit assumptions"

**Rubric dimensions:**

| Dimension | What it checks | Severity |
|---|---|---|
| Evidence coverage | Every non-trivial parameter has provenance? Any `[UNVERIFIED]` or `sci:Unknown` remaining? | Error if unknowns, warn if unverified |
| Assumption audit | All causal claims justified? Confounders identified? Direction justified? | Error if unjustified causal |
| Data availability | All `BoundaryIn` data sources accessible? Formats specified? | Error if inaccessible |
| Identifiability | Every `BoundaryOut` reachable from `BoundaryIn`? No disconnected subgraphs? | Error |
| Reproducibility | Seeds, versions, environments specified? Determinism achievable? | Warn |
| Validation criteria | Every `sci:Transformation` has a `sci:validatedBy` check? | Warn |
| Scope check | Inquiry stays within `specs/scope-boundaries.md`? | Warn |

**Output:** Review report saved to `doc/inquiries/<slug>-review.md` with pass/warn/fail per dimension, specific actionable items, and a summary recommendation.

**Agent review mode:** The reviewing agent operates as a `discussant` role — critical, looking for weaknesses, not rubber-stamping. It should surface:
- Missing confounders
- Unjustified parameter choices
- Circular reasoning (A justifies B which justifies A)
- Scope creep relative to the target hypothesis
- Untested assumptions

---

## 4. Ontology Extensions

### 4.1 New Types

| Type | Purpose | Layer |
|---|---|---|
| `sci:Inquiry` | Named subgraph container for an investigation | `:inquiry/<slug>` |
| `sci:Variable` | A quantity in the model (observed, latent, or computed) | `:graph/knowledge` |
| `sci:Transformation` | A computational/analytical step | `:inquiry/<slug>` |
| `sci:Assumption` | An explicit modeling assumption with provenance | `:graph/knowledge` |
| `sci:Unknown` | Placeholder for unidentified factors (sketch only) | `:inquiry/<slug>` |
| `sci:ValidationCheck` | A criterion for verifying a step or result | `:inquiry/<slug>` |

### 4.2 New Predicates

| Predicate | Description | Layer |
|---|---|---|
| `sci:target` | Links inquiry to its hypothesis/question | `:inquiry/*` |
| `sci:boundaryRole` | Assigns boundary classification (BoundaryIn/BoundaryOut) within an inquiry | `:inquiry/*` |
| `sci:inquiryStatus` | Inquiry lifecycle status (sketch/specified/planned/in-progress/complete) | `:inquiry/*` |
| `sci:feedsInto` | Data/information flow: A provides input to B | `:inquiry/*` |
| `sci:assumes` | Marks a dependency on an assumption | `:inquiry/*` |
| `sci:produces` | A transformation yields an output | `:inquiry/*` |
| `sci:paramValue` | Parameter value (literal) | `:inquiry/*` |
| `sci:paramSource` | Parameter source type (literature/empirical/design_decision/convention/data_derived) | `:inquiry/*` |
| `sci:paramRef` | Parameter reference (BibTeX key or doc path) | `:inquiry/*` |
| `sci:paramNote` | Parameter rationale note | `:inquiry/*` |
| `sci:observability` | Whether a variable is observed, latent, or computed | `:graph/knowledge` |
| `sci:validatedBy` | Links a step to its validation criterion | `:inquiry/*` |

### 4.3 New Boundary Role Values

| Value | URI | Meaning |
|---|---|---|
| BoundaryIn | `sci:BoundaryIn` | Given/observable input to the inquiry |
| BoundaryOut | `sci:BoundaryOut` | Produced output of the inquiry |

### 4.4 Compatibility

These extensions are additive — they don't modify existing predicates or types. Existing graphs remain valid. The new `:inquiry/*` named graphs are orthogonal to existing `:graph/*` layers.

---

## 5. Graph Store Changes

### 5.1 New Methods on `GraphStore`

```python
def add_inquiry(self, slug: str, label: str, target: str,
                description: str = "", status: str = "sketch") -> URIRef:
    """Create a new inquiry named graph with metadata."""

def set_boundary_role(self, inquiry_slug: str, entity: str,
                      role: str) -> None:
    """Assign BoundaryIn or BoundaryOut role to an entity within an inquiry."""

def add_inquiry_edge(self, inquiry_slug: str, subject: str,
                     predicate: str, obj: str) -> None:
    """Add an edge within an inquiry subgraph."""

def add_assumption(self, label: str, source: str,
                   inquiry_slug: str | None = None) -> URIRef:
    """Add an assumption entity, optionally within an inquiry."""

def add_transformation(self, label: str, inquiry_slug: str,
                       tool: str = "", params: dict | None = None) -> URIRef:
    """Add a transformation step within an inquiry."""

def set_param_metadata(self, entity: str, value: str,
                       source: str, refs: list[str] | None = None,
                       note: str = "") -> None:
    """Attach AnnotatedParam-style metadata to an entity."""

def get_inquiry(self, slug: str) -> dict:
    """Return inquiry metadata, nodes, edges, and boundary roles."""

def list_inquiries(self) -> list[dict]:
    """List all inquiry subgraphs with basic metadata."""

def validate_inquiry(self, slug: str) -> list[dict]:
    """Run inquiry-specific validation checks."""
```

### 5.2 New CLI Subcommands

```
science-tool inquiry init <SLUG> --label <LABEL> --target <HYPOTHESIS_OR_QUESTION>
                                 [--description <TEXT>] [--status sketch]

science-tool inquiry add-node <SLUG> <ENTITY> --role <BoundaryIn|BoundaryOut|interior>

science-tool inquiry add-edge <SLUG> <SUBJECT> <PREDICATE> <OBJECT>

science-tool inquiry add-assumption <SLUG> <LABEL> --source <REF>

science-tool inquiry add-transformation <SLUG> <LABEL> [--tool <TOOL>]
                                        [--param <KEY> <VALUE> --param-source <TYPE>
                                         --param-ref <REF> --param-note <NOTE>]

science-tool inquiry list [--format table|json]

science-tool inquiry show <SLUG> [--format table|json]

science-tool inquiry validate <SLUG> [--format table|json]

science-tool inquiry viz <SLUG> [--output <FILE>]
```

### 5.3 Predicate Registry Updates

Add new predicates to `PREDICATE_REGISTRY` in `store.py`:

```python
{"predicate": "sci:target", "description": "Inquiry targets hypothesis/question", "layer": "inquiry"},
{"predicate": "sci:boundaryRole", "description": "Boundary classification within inquiry", "layer": "inquiry"},
{"predicate": "sci:inquiryStatus", "description": "Inquiry lifecycle status", "layer": "inquiry"},
{"predicate": "sci:feedsInto", "description": "Data/information flow", "layer": "inquiry"},
{"predicate": "sci:assumes", "description": "Dependency on assumption", "layer": "inquiry"},
{"predicate": "sci:produces", "description": "Transformation yields output", "layer": "inquiry"},
{"predicate": "sci:paramValue", "description": "Parameter value", "layer": "inquiry"},
{"predicate": "sci:paramSource", "description": "Parameter source type", "layer": "inquiry"},
{"predicate": "sci:paramRef", "description": "Parameter reference", "layer": "inquiry"},
{"predicate": "sci:paramNote", "description": "Parameter rationale", "layer": "inquiry"},
{"predicate": "sci:observability", "description": "Variable observability status", "layer": "graph/knowledge"},
{"predicate": "sci:validatedBy", "description": "Step validated by criterion", "layer": "inquiry"},
```

---

## 6. File System Artifacts

### 6.1 New Directories and Files

```
doc/inquiries/                     # Human-readable inquiry documents
├── <slug>.md                      # Rendered view of inquiry subgraph
└── <slug>-review.md               # Review report (from review-pipeline)

templates/
└── inquiry.md                     # Template for inquiry documents
```

### 6.2 Inquiry Document Template

The inquiry doc is a **rendered view** of the subgraph — not a separate source of truth. The graph is canonical. The doc is regenerated each time the inquiry is modified.

```markdown
# Inquiry: {{label}}

- **Slug:** {{slug}}
- **Target:** {{target_label}} ({{target_id}})
- **Status:** {{status}}
- **Created:** {{created}}
- **Last updated:** {{updated}}

## Summary

{{description}}

## Variables

### Boundary In (Givens)

| Variable | Type | Data Source | Provenance |
|---|---|---|---|
| {{label}} | {{type}} | {{source}} | {{refs}} |

### Boundary Out (Produces)

| Variable | Type | Format | Validation |
|---|---|---|---|
| {{label}} | {{type}} | {{format}} | {{check}} |

### Interior (Latent/Computed)

| Variable | Type | Observability | Notes |
|---|---|---|---|
| {{label}} | {{type}} | {{obs}} | {{note}} |

## Relationships

{{rendered edge list with types and provenance}}

## Assumptions

| Assumption | Evidence | Confidence |
|---|---|---|
| {{label}} | {{source}} | {{confidence}} |

## Unknowns

| Unknown | Context | Plan to Resolve |
|---|---|---|
| {{label}} | {{where_in_graph}} | {{plan}} |

## Parameters

| Parameter | Value | Source | References | Note |
|---|---|---|---|---|
| {{name}} | {{value}} | {{source_type}} | {{refs}} | {{note}} |

## Visualization

{{graph viz output or path to generated image}}
```

---

## 7. Validation Extensions

### 7.1 New `validate.sh` Checks (Section 14)

```
14. Inquiry validation
  14a. Inquiry parse — all :inquiry/* named graphs are parseable
  14b. Boundary reachability — every BoundaryOut reachable from some BoundaryIn
  14c. Orphaned interior — interior nodes with no incoming or outgoing edges
  14d. Unknown resolution — sketches may have sci:Unknown; specified+ must not
  14e. Provenance completeness — specified+ inquiries: all assumptions have sources
  14f. Target validity — inquiry target node exists as a hypothesis or question
```

### 7.2 `science-tool inquiry validate` Checks

| Check | Status threshold | Description |
|---|---|---|
| `boundary_reachability` | Error | Every BoundaryOut must be reachable from at least one BoundaryIn via directed edges |
| `orphaned_interior` | Warning | Interior nodes disconnected from both boundary sets |
| `unknown_resolution` | Error (if specified+) | `sci:Unknown` nodes must be resolved or justified |
| `provenance_completeness` | Error (if specified+) | All assumptions and claims must have `prov:wasDerivedFrom` |
| `target_exists` | Error | Target hypothesis/question must exist in `:graph/knowledge` |
| `no_cycles` | Error | `sci:feedsInto` edges must form a DAG within the inquiry |

---

## 8. Integration with Existing Commands

| Existing command | Integration |
|---|---|
| `/science:add-hypothesis` | Creates hypothesis nodes that can become inquiry targets |
| `/science:create-graph` | Inquiry entities appear in `:graph/knowledge`; create-graph naturally includes them |
| `/science:update-graph` | Inquiry subgraphs included in `graph diff` staleness detection |
| `/science:discuss` | Can take an inquiry slug as `focus_ref` for structured critique |
| `/science:research-gaps` | Inquiries with `sci:Unknown` nodes surface as gaps |
| `validate.sh` | Section 14 added for inquiry-specific checks |

---

## 9. Worked Example: seq-feats Signal Peptide Inquiry

To ground the abstraction, here's how the seq-feats signal peptide analysis would look as an inquiry:

**Target:** H03 — "Embedding geometry reflects structural/functional properties"

**Sketch:**
```
uniprot_reviewed_sps [BoundaryIn] → sp_sequences → sp_embeddings → distance_matrix [BoundaryOut]
esm2_650m [BoundaryIn] → sp_embeddings
random_controls → control_embeddings → control_distances [BoundaryOut]
sp_sequences → random_controls
```

**Specified** (adds types, provenance, parameters):
- `uniprot_reviewed_sps`: `sci:Variable`, observed, source=UniProt, `sci:measuredBy dataset:uniprot_reviewed`
- `esm2_650m`: `biolink:GeneticModel`, BoundaryIn, source=`paper:doi_10_1101_2022_07_20_500902`
- `mean_pooling_sufficient`: `sci:Assumption`, source=paper + empirical pilot data
- Pooling parameter: value=`mean`, source=`design_decision`, ref=`doc/04-approach.md`, note="captures SP-relevant info; validated in pilot"
- Control count: value=10, source=`convention`, ref=`specs/control-framework.md#section-3`, note="pilot; full study uses 100"

**Planned** (adds transformations):
- `extract_sequences`: `sci:Transformation`, tool=BioPython, input=UniProt query, output=FASTA
- `embed_sequences`: `sci:Transformation`, tool=`seq-feats embed`, params={model, pooling, layers, batch_size, seed}
- `generate_controls`: `sci:Transformation`, tool=`seq-feats controls t1`, params={n, seed}
- Each transformation has `sci:validatedBy` checks (sequence count, embedding shape, determinism)

---

## 10. Design Decisions

1. **Graph-native, not graph-optional.** Inquiries live in the knowledge graph as named subgraphs. This ensures consistency with the overall project model and explicitly connects research models with KG entities. The commands abstract away graph operations — users interact conversationally, not with raw graph commands.

2. **Boundary nodes are per-inquiry, not intrinsic.** A node's role as input/output depends on which inquiry you're looking at. This enables composability: the same dataset can be a given in one inquiry and a product in another.

3. **Sketch before specify.** Two separate cognitive modes with different quality bars. Sketches allow `sci:Unknown` nodes and untyped edges; specifying resolves these. This prevents the formalization step from blocking initial exploration.

4. **AnnotatedParam as graph properties, not a separate config system.** Parameter provenance lives on graph entities, not in standalone YAML files. Projects that need YAML configs (like seq-feats) generate them from graph data — the graph is the source of truth.

5. **Review as rubric, not checkbox.** The review command uses a discussant role to find weaknesses, not just verify structural completeness. Structural checks are in `validate.sh`; the review command adds scientific scrutiny.

6. **Inquiry docs are rendered views.** The `doc/inquiries/<slug>.md` file is regenerated from the graph, not manually maintained. The graph is canonical. This prevents drift between prose and graph representations.

7. **Additive ontology extensions.** New types and predicates don't modify existing ones. Existing graphs remain valid. Inquiry named graphs are orthogonal to existing `:graph/*` layers.

---

## 11. Non-Goals (Explicit)

- **Tool-specific pipeline generation.** Snakemake/Nextflow/Marimo specifics are separate skills (`skills/pipelines/*.md`), not part of the inquiry workflow. `plan-pipeline` references these skills but doesn't embed their logic.
- **Automated entity matching.** Inquiries don't auto-link to external ontologies. Users/agents assign types manually.
- **Multi-inquiry composition rules.** Typed inquiry patterns (data→variable→hypothesis) are a future extension. Start with the bare abstraction; let usage reveal which patterns recur.
- **Probabilistic parameter models.** Layer 3 provenance (PyMC/Pyro) is future work. The `AnnotatedParam` property structure is designed to be forward-compatible.
- **Execution orchestration.** The inquiry workflow designs pipelines; it doesn't run them. Execution is a separate concern (Snakemake, manual, CI/CD).

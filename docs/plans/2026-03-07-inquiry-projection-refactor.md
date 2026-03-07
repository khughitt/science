# Deferred Refactor: Inquiries as Pure Projections

*Date: 2026-03-07*
*Status: Deferred*
*Prerequisite: Phase 4b causal DAG implementation (validates the pattern)*

## Motivation

The current inquiry implementation stores edges *inside* inquiry named graphs (`:inquiry/<slug>`). For example, `sci:feedsInto` edges between variables live in the inquiry subgraph. This creates several issues:

1. **Duplication.** If two inquiries share a relationship (e.g., "dataset X feeds into model Y"), the edge must be declared in both inquiry graphs independently. There is no single source of truth.

2. **Inconsistency risk.** An edge updated in `graph/knowledge` or `graph/causal` is not automatically reflected in inquiries that encode the same relationship. The inquiry copy can drift from the canonical representation.

3. **False distinction between "established" and "working" knowledge.** The current design implies that edges in `graph/causal` are somehow more authoritative than edges in an inquiry. In practice, both represent beliefs with varying degrees of evidence — from a researcher's hunch (low confidence, few sources) to well-established findings (high confidence, many independent replications). The difference is quantitative (confidence, evidence depth), not qualitative (different storage location).

4. **Mental model complexity.** Users must understand which edges live where. "Is this causal edge in `graph/causal` or in my inquiry?" The answer should be: all domain edges live in the KG; inquiries are views.

## Vision

**Inquiries become pure projections (views) over the knowledge graph.** An inquiry defines:
- Which entities are *in scope* (membership)
- What *role* each entity plays (boundary in/out, treatment/outcome)
- What the *investigation target* is (hypothesis, question)
- What *status* the investigation is in (sketch, specified, planned, etc.)

An inquiry does **not** contain domain edges. Instead, the inquiry's "subgraph" is computed at query time by filtering KG layers to the inquiry's entity set.

### Current Model

```
graph/knowledge:  entities, associative edges (skos:related, sci:usesComponent, ...)
graph/causal:     scic:causes, scic:confounds
graph/provenance: claims, sources
inquiry/<slug>:   boundary roles, metadata, AND sci:feedsInto edges, AND some domain edges
```

### Target Model

```
graph/knowledge:  entities, associative edges, sci:feedsInto edges
graph/causal:     scic:causes, scic:confounds
graph/provenance: claims, sources
inquiry/<slug>:   boundary roles, metadata, entity membership ONLY
```

### How Inquiry Views Work

An inquiry's effective subgraph is computed by:

```python
def get_inquiry_subgraph(graph_path, slug):
    members = get_inquiry_members(slug)       # entities with boundary roles or membership
    knowledge_edges = filter_edges("graph/knowledge", subjects_or_objects_in=members)
    causal_edges = filter_edges("graph/causal", subjects_or_objects_in=members)
    return members, knowledge_edges, causal_edges
```

This replaces the current approach of reading edges directly from the inquiry named graph.

## What Needs to Change

### 1. Entity Membership Mechanism

Currently, entities are implicitly "in" an inquiry because edges reference them. With edges moved upstream, we need explicit membership:

```turtle
:inquiry/my-study {
    inquiry:my_study a sci:Inquiry ;
        sci:inquiryType "causal" ;
        sci:target hypothesis:h01 .

    # Membership declarations
    concept:X sci:memberOf inquiry:my_study .
    concept:Y sci:memberOf inquiry:my_study .
    concept:Z sci:memberOf inquiry:my_study .

    # Roles (unchanged)
    concept:X sci:boundaryRole sci:BoundaryIn .
    concept:Y sci:boundaryRole sci:BoundaryOut .
}
```

New predicate: `sci:memberOf` — declares that an entity participates in this inquiry.

### 2. Move `sci:feedsInto` Upstream

`sci:feedsInto` edges currently live in inquiry graphs. They need to move to `graph/knowledge`. This is straightforward — `feedsInto` represents data/computational flow between entities, which is a domain relationship.

**Consideration:** If two inquiries share the same variables but have different computational flows (different estimation procedures for the same causal question), the `feedsInto` edges would conflict. Solutions:
- **Option A:** Accept that `feedsInto` edges are shared. Different procedures mean different variables (e.g., `regression_estimate_v1` vs. `bayesian_estimate_v2`).
- **Option B:** Allow inquiry-scoped `feedsInto` edges as an exception to the pure-projection model.
- **Recommendation:** Start with Option A. If real usage shows conflicts, add Option B as a targeted exception.

### 3. Update Store Methods

- `add_inquiry_edge()` → adds edges to the appropriate KG layer (`graph/knowledge` or `graph/causal`) instead of the inquiry graph, and adds membership for both endpoints
- `get_inquiry()` → computes the effective subgraph by filtering KG layers to members
- `validate_inquiry()` → queries across layers instead of just the inquiry graph

### 4. Update CLI Commands

- `inquiry add-edge` → behavior changes (adds to KG layer + membership), but interface stays the same
- `inquiry show` → displays the computed projection, not raw inquiry graph contents
- New: `inquiry add-member <SLUG> <ENTITY>` — explicit membership without an edge

### 5. Migration

Existing inquiry graphs with embedded edges need migration:
1. For each inquiry, extract `sci:feedsInto` and other domain edges
2. Move them to the appropriate KG layer
3. Add `sci:memberOf` triples for all referenced entities
4. Remove domain edges from inquiry graph

This can be a one-time migration script or a `science-tool graph migrate` command.

## What Does NOT Change

- Inquiry named graphs still exist (for metadata, roles, membership)
- `inquiry init`, `inquiry validate`, `inquiry show` — same interface
- Slash commands (`build-dag`, `sketch-model`, etc.) — same workflows
- Export commands — same output, different internal query path
- `validate.sh` checks — same semantics

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Membership bookkeeping overhead | CLI commands auto-add membership when adding edges; users never manually manage it |
| Computed views are slower than direct graph reads | Cache inquiry projections; re-compute on `graph diff` staleness |
| `feedsInto` conflicts between inquiries | Start with shared edges (Option A); add scoped exception if needed |
| Migration breaks existing projects | Version the graph format; provide automated migration |

## When to Execute

Execute this refactor when:
- Phase 4b is complete and validated (causal DAGs work as typed inquiries)
- At least 2-3 inquiries exist across exemplar projects (enough usage data to validate the projection model)
- A second inquiry type emerges (beyond `general` and `causal`), confirming the pattern generalizes

Do **not** execute preemptively. The current model works for Phase 4b. This refactor improves consistency and simplicity but is not blocking.

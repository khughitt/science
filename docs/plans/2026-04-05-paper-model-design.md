# Paper Model Design

> Depends on: [`2026-04-05-project-model-design.md`](./2026-04-05-project-model-design.md) (defines the entity types and relations this spec composes).
> Motivation: Science projects lack a compositional structure for organizing findings into coherent narratives and communicable research documents.

## Summary

The Paper Model defines how compositional entities from the Project Model (finding,
interpretation, story, paper) assemble into a communicable research document. It specifies
the tree-structured composition, the relationship between conventional paper sections and
stories, and the iterative workflow for assembling and refining papers.

The Paper Model is a composition pattern over the Project Model — it does not introduce new
entity types, only rules and conventions for how existing entities relate.

## Goals

- Define how findings compose into interpretations, stories, and papers.
- Support bottom-up assembly (findings accumulate → stories emerge → papers form) and
  top-down refinement (paper outline → gap analysis → targeted investigation).
- Keep the framework focused on structure and traceability, not prose generation.
- Make figures, tables, and other visual outputs properties of findings, not standalone entities.
- Allow the same finding to appear in multiple papers without duplication.

## Non-Goals

- Generate publication-ready prose.
- Enforce a rigid paper template or mandate specific sections.
- Auto-compose papers from findings. Assembly is an intentional, creative act.
- Define domain-specific reporting conventions (e.g., CONSORT for clinical trials).

## Design

### Composition Structure

A paper is a tree, not a flat list. Paper sections can nest, stories can have sub-narratives,
and the conventional paper structure maps onto this as labeled branches.

```
paper
  ├── section: introduction
  │     └── prose (background, motivation, aims)
  │           └── references propositions + questions from the graph
  ├── section: methods
  │     └── prose (approach descriptions)
  │           └── references methods, workflows, datasets
  ├── section: results
  │     ├── story: "X regulates Y"
  │     │     ├── interpretation: initial expression analysis
  │     │     │     ├── finding: differential expression in condition A
  │     │     │     └── finding: pathway enrichment points to Y
  │     │     └── interpretation: validation experiment
  │     │           └── finding: knockdown confirms regulation
  │     └── story: "Z modulates the X-Y interaction"
  │           └── interpretation: interaction analysis
  │                 └── finding: Z concentration alters effect size
  ├── section: discussion
  │     └── prose (synthesis, limitations, future directions)
  │           └── references propositions, questions (especially open ones)
  └── bibliography
```

### Sections

Sections are lightweight — just labels, ordering, and prose. A section is NOT a separate entity
type. It is a property of the paper: a named, ordered slot that can contain:

- **Story refs** (for results-heavy sections)
- **Prose** (for narrative-heavy sections like introduction, discussion)
- **Both** (for sections that mix narrative with structured findings)

This avoids over-formalizing paper structure while keeping it navigable.

### Figures and Tables

Figures and tables are properties of findings or observations, not standalone entities:

- A **figure** is a visualization of an observation or set of observations.
- A **table** is a structured presentation of observations.

They are referenced by findings and rendered in the paper context. They don't need their own
entity type because their epistemic content is already captured in the observations and
findings they visualize.

Figures and tables link to the `data_package` that contains their source data, preserving
full traceability: paper → story → interpretation → finding → observation → data_package
→ workflow_run → code.

### The Paper as a View

The paper's value is in what it *points to*, not what it *contains*. The paper itself holds
minimal unique content — just ordering, section labels, and connective prose. The real
substance lives in the graph: propositions, observations, findings.

The paper is a *view* over the knowledge graph, organized for communication. This means:

- **Rearranging a paper doesn't lose knowledge.** All epistemic content is in the graph.
- **The same finding can appear in multiple papers.** No duplication of evidence or claims.
- **Iterating on a paper is iterating on its composition, not its content.** You change what
  to include and how to order it; the underlying findings remain stable.

## Iteration and Assembly Workflow

### Bottom-Up Assembly (the natural research flow)

Research doesn't start with a paper outline. It starts with analysis that produces findings:

1. Run a pipeline → `workflow_run` produces `data_package`.
2. `interpret-results` examines outputs → creates `observations`, `findings`, and an
   `interpretation`.
3. Findings accumulate. Related findings cluster around questions and hypotheses.
4. When enough findings cohere around a question, a `story` forms.
5. When enough stories exist, a `paper` outline can be sketched.

### Top-Down Refinement (the communication flow)

Once a paper outline exists, it reveals gaps:

1. A story feels incomplete → which findings are missing? → what observations would
   you need? → what analysis would produce them?
2. A section lacks coherence → which stories need better connective prose? → which
   propositions need stronger evidence?
3. Gap analysis becomes concrete: "story S is missing a finding about X, which requires
   running workflow W on dataset D."

### The Iterate-on-Stories Pattern

The primary unit of iteration is the story. Working on a paper means:

1. Pick a story in `draft` or `developing` status.
2. Review its interpretations and findings for gaps.
3. Run analyses to fill gaps (produces new findings).
4. Refine the story's synthesis prose.
5. Assess whether the story is `mature` enough.
6. Move to the next story.

### Illustrative Commands

These commands are illustrative of what the model enables. Exact command design is an
implementation concern.

| Action | Produces | Starting from |
|--------|----------|---------------|
| `interpret-results` | observations, findings, interpretation | workflow output or data |
| `assemble-story` | story | question/hypothesis + accumulated interpretations |
| `outline-paper` | paper skeleton | set of stories |
| `paper-gaps` | gap analysis | paper outline |
| `story-status` | maturity assessment | story |

### What the Framework Should NOT Do

- **Generate publication-ready prose.** The framework manages structure and traceability;
  writing remains human work.
- **Enforce a rigid paper template.** Sections are flexible labels, not a mandated structure.
- **Auto-compose papers from findings.** Assembly is an intentional, creative act. The
  framework surfaces what you have and what's missing; you decide how to arrange it.

## Composition Patterns

### Single-Paper Project

The simplest case: one project, one paper.

```
project
  └── paper: "Effect of X on Y"
        ├── story: "X regulates Y" (mature)
        ├── story: "mechanism involves Z" (developing)
        └── story: "clinical implications" (draft)
```

### Multi-Paper Project

Larger projects may produce multiple papers from the same knowledge base.

```
project
  ├── paper: "X-Y Regulation Mechanism" (methods paper)
  │     └── story: "novel assay for X measurement"
  ├── paper: "X in Disease Context" (clinical paper)
  │     ├── story: "X-Y dysregulation in disease"
  │     └── story: "therapeutic targeting of X"
  └── (shared knowledge graph with all findings)
```

The same findings and observations can appear in multiple papers. The graph is the single
source of truth; papers are views over it.

### Progressive Maturity

Stories and papers have explicit status fields that track maturity:

| Entity | Statuses | Semantics |
|--------|----------|-----------|
| Story | `draft → developing → mature` | How complete and cohesive the narrative is |
| Paper | `outline → draft → revision → final` | How close to communicable the paper is |

Status transitions are author-driven, not automated. The framework can *suggest* that a
story's findings are thin or a paper has structural gaps, but the human decides when to
advance status.

## Relationship to Existing Skills

| Current Skill | How It Changes |
|---------------|---------------|
| `interpret-results` | Now produces structured `observations` + `findings` + `interpretation` entities instead of (or alongside) prose documents |
| `add-hypothesis` | Unchanged; hypotheses bundle propositions (formerly claims) |
| `sketch-model` / `specify-model` | Unchanged; models connect variables to propositions via domain bridge |
| `compare-hypotheses` | May produce findings that feed into stories |
| `discuss` | Design question (deferred in Project Model spec) |
| `next-steps` | Can now include paper/story gap analysis |
| `status` | Can now include paper/story maturity summary |

New skills/commands that this model enables are an implementation concern and not prescribed
by this spec.

# Entities

An entity is a durable typed record in a Science project. Most entities are
Markdown files with YAML frontmatter and body prose. The frontmatter provides
machine-readable identity and relationships; the body provides human-readable
context.

## Entity Shape

```markdown
---
id: proposition:example
type: proposition
title: "Example proposition"
status: draft
related:
  - hypothesis:h01-example
source_refs:
  - paper:Example2026
created: "2026-06-20"
updated: "2026-06-20"
---

# Example proposition

This body explains the proposition, scope, caveats, and evidence needs.
```

Important fields:

| Field | Purpose |
|---|---|
| `id` | Stable typed reference, usually `<kind>:<local-part>`. |
| `type` | Entity kind. Usually matches the prefix in `id`. |
| `title` | Human-readable title. |
| `status` | Lifecycle state for the kind. |
| `related` | Other entity refs connected to this record. |
| `source_refs` | Sources or annotations that support the existence or content of this record. |
| Body prose | Explanation, caveats, rationale, and review context. |

## Authored And Derived Fields

Authored fields are recorded directly in source files. Derived fields are
computed from the graph, evidence, provenance, or health machinery. Belief
state, support summaries, dispute summaries, freshness, and health status should
be recomputed rather than manually patched.

## Entity Classes

Science groups core entity kinds into three classes.

### Epistemic

Epistemic entities carry, organize, or evaluate uncertain knowledge.

<!-- entity-kinds:epistemic:start -->
- `assumption` - An explicit assumption underpinning a model, analysis, or argument.
- `chain-audit` - Verdict over a structural-chain. Carries verdict+bayes_factor_evidence with enforced consistency.
- `discussion` - Structured critical discussion of a hypothesis, question, or topic.
- `evidence-line` - A single, independence-tagged line of evidence that supports or disputes a proposition.
- `finding` - Unit of learned knowledge: propositions grounded by observations from an analysis.
- `hypothesis` - Testable project hypothesis.
- `inquiry` - A scoped research inquiry (boundary + estimand over the knowledge graph).
- `interpretation` - One analysis session's narrative and its findings.
- `mechanism` - Named explanatory structure linking multiple typed entities and propositions.
- `observation` - Concrete empirical fact anchored to specific data.
- `patch-definition` - Authored patch profile asserting a belief membership over the graph.
- `proposition` - Truth-apt statement - the fundamental epistemic unit.
- `question` - Open or resolved project question.
- `report` - Standalone written report over project knowledge.
- `research-question` - The project's single guiding research question.
- `story` - Coherent narrative arc synthesizing interpretations around a question or hypothesis.
- `structural-chain` - Ordered structural decomposition: >=2 entity refs forming a chain whose verdicts are carried by chain-audit.
- `synthesis` - Cross-cutting synthesis rolling up interpretations and findings.
- `theme` - Durable cross-cutting organizing frame linking project questions, hypotheses, tasks, reports, concepts, and guardrails.
- `validation-report` - Report validating an analysis, model, or pipeline result.
<!-- entity-kinds:epistemic:end -->

### Operational

Operational entities describe work products, sources, runs, plans, datasets, and
project machinery.

<!-- entity-kinds:operational:start -->
- `book` - Long-form monograph summarized chapter-by-chapter; an evidence source.
- `claim-registry` - The project's single registry of tracked external claims.
- `code-file` - Source-code file implementing workflow steps and methods.
- `curation-sweep` - A project-memory curation sweep tracked as an operational artifact.
- `data-package` - Frictionless research package containing analysis results, prose, and provenance metadata.
- `dataset` - Tabular or file dataset tracked as a research artifact.
- `experiment` - Experiment or analysis step that tests project questions.
- `method` - Analytical method or computational approach.
- `paper` - Ordered composition of stories structured for communication.
- `plan` - An authored implementation or analysis plan.
- `pre-registration` - Pre-registered analysis plan stating expectations before analysis.
- `prose-source` - Authored internal Markdown prose used as an operational evidence source.
- `research-package` - Composed research package bundling analysis results and provenance.
- `search` - A literature or dataset search and its recorded results.
- `spec` - A design or implementation specification.
- `talk` - Recorded seminar or conference presentation; an unrefereed evidence source.
- `task` - Operational project task tracked in the graph.
- `transformation` - A data transformation applied within an analysis.
- `workflow` - Reusable pipeline definition (Snakefile + config + rules).
- `workflow-run` - Concrete execution of a workflow producing durable outputs.
- `workflow-step` - Individual step within a workflow definition or run.
<!-- entity-kinds:operational:end -->

### Reference

Reference entities name concepts, variables, outcomes, sources, decisions, and
other stable objects that the project points at.

<!-- entity-kinds:reference:start -->
- `article` - External article or document referenced as a source.
- `concept` - A named concept referenced across the project.
- `construct` - A theoretical construct operationalized by the project.
- `decision` - A recorded project decision with rationale.
- `outcome` - A measured or targeted outcome variable.
- `topic` - A research topic synthesized from the literature.
- `unknown` - Built-in sentinel kind for unrecognized entities.
- `variable` - A modeled variable in an analysis or causal model.
<!-- entity-kinds:reference:end -->

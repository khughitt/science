# Natural-Systems-Guide Claim-Centric Uncertainty Migration Guide

Project: `/home/keith/d/mindful/natural-systems-guide`

## Why This Migration Is Different

`natural-systems-guide` already has a stronger KG migration story than the other two projects:

- it already has `/home/keith/d/mindful/natural-systems-guide/kg-project-migration-guide.md`
- it already uses multiple structured source files under `knowledge/sources/project_specific/`
- it already treats the graph as a first-class product artifact

So this migration is not about basic graph hygiene. It is about layering a reasoning model on top of an already structured graph.

## Current Shape

Relevant files:

- `/home/keith/d/mindful/natural-systems-guide/kg-project-migration-guide.md`
- `/home/keith/d/mindful/natural-systems-guide/knowledge/sources/project_specific/entities.yaml`
- `/home/keith/d/mindful/natural-systems-guide/knowledge/sources/project_specific/relations.yaml`
- `/home/keith/d/mindful/natural-systems-guide/doc/questions/`
- `/home/keith/d/mindful/natural-systems-guide/doc/interpretations/`
- `/home/keith/d/mindful/natural-systems-guide/docs/plans/2026-03-13-kg-migration-plan.md`

Observed migration pressure:

- the project already has many typed model/parameter/limit/composition entities
- reasoning about cross-model relationships still often lives in question/discussion prose
- `cito:discusses` links to questions are present, but they are not yet a full claim/evidence layer
- some “relationship quality” questions should become explicit uncertain claims

## Migration Goal

Preserve the existing model-centric KG, but add a claim/evidence overlay for uncertain cross-model assertions such as:

- model A is structurally analogous to model B
- parameter-mediated bridges represent genuine shared structure rather than naming accidents
- disagreement clusters reveal real multi-lens tension rather than metadata noise

This project should not become hypothesis-heavy. It should become claim-explicit where the project is already making uncertain interpretive assertions.

## Recommended First Migration Targets

Start in this order:

1. questions about relationship quality and model linkage:
   - `q03`
   - `q05`
   - `q18`
   - `q27`
2. interpretation docs under `/home/keith/d/mindful/natural-systems-guide/doc/interpretations/`
3. only then broader category-theoretic and meta-model questions

Reason:

- these are the places where the project is most clearly making uncertain structural claims
- they are also the places where dashboard prioritization could guide curation effort

## Suggested Claim Decomposition

Useful first-pass claim shapes:

- a discovered model-to-model relationship reflects real shared structure
- a proposed bridge is supported by multiple independent lenses
- a parameter match is likely spurious
- a disagreement cluster indicates missing ontology cleanup rather than substantive scientific tension
- a compositional relation is robust across source layers

These should be represented as claims about relationships, not just as `relatedTo` edges or open questions.

## Evidence Migration Rules

Use these mappings:

- published papers already linked via `cito:discusses` -> `literature_evidence`
- derived reports and analyses in `/home/keith/d/mindful/natural-systems-guide/doc/reports/` and `/home/keith/d/mindful/natural-systems-guide/doc/interpretations/` -> `empirical_data_evidence` if they summarize project-run computations over the registry/graph
- audits showing false positives or metadata problems -> `negative_result` or disputing evidence
- category-theoretic framing notes -> usually motivation or claim text, not evidence by themselves

## Concrete Migration Steps

1. Keep the existing KG migration baseline; do not redo canonical-ID migration.
2. Identify the highest-value uncertain relationship claims in questions like `q05`, `q18`, and `q27`.
3. Create explicit claims for those assertions instead of relying only on question prose and `cito:discusses`.
4. Attach supporting/disputing evidence from project-run reports and interpretations.
5. Use dashboard outputs to prioritize relationship clusters that are:
   - single-source
   - contested
   - unsupported by project-run analyses

## Success Criteria

The migration is successful when:

- the graph can distinguish “interesting open question” from “explicit but weakly supported relationship claim”
- disagreement-heavy regions become queryable and prioritizable
- literature-backed claims and project-analysis-backed claims are visibly different in dashboard summaries
- ontology cleanup work can be directed toward the highest-risk relationship neighborhoods

## Recommended Validation Commands

Run in `/home/keith/d/mindful/natural-systems-guide`:

```bash
uv run --frozen science-tool graph audit --project-root . --format json
uv run --frozen science-tool graph build --project-root .
uv run --frozen science-tool graph validate --format json --path knowledge/graph.trig
uv run --frozen science-tool graph dashboard-summary --path knowledge/graph.trig --format json
```

## Main Risk

The biggest migration mistake here would be importing hypothesis-style workflow too literally. This project is fundamentally about model relationships and structural analogies, so the claim layer should be added where it increases rigor, not where it forces artificial biomedical-style hypothesis machinery onto every part of the guide.

---
id: "theme:{{slug}}"
type: "theme"
title: "{{title}}"
status: "{{status}}"
theme_kind: "methodological"  # methodological | conceptual | empirical | domain. Active profiles may extend or replace this enum — check the project's resolved schema (or `science-tool entity sections theme` once it surfaces frontmatter constraints) for accepted values. Canonical enum lives in schemas/mixin-theme-2.0.json.
theme_scope: "project"  # project | cross-project. `project` for themes local to a single Science project; `cross-project` for themes organized at the federation/meta level.
related: []
source_refs: []
# origins: known originators (user | assistant | literature). Provenance only;
# does not affect belief. literature ref must be paper:<key> or cite:<key>.
origins: []
evidence_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "theme" }
    title: { from: title }
    status: { from: status }
    theme_kind: { default: "methodological" }
    theme_scope: { default: "project" }
    related: { from: related }
    source_refs: { from: source_refs }
    origins: { from: origins, default: [] }
    evidence_refs: { default: [] }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: definition, name: "Definition", required: true }
    - { key: why-it-matters, name: "Why It Matters", required: true }
    - { key: boundaries, name: "Boundaries", required: true }
    - { key: current-project-links, name: "Current Project Links", required: true }
    - { key: guardrails, name: "Guardrails", required: true }
    - { key: downstream-work, name: "Downstream Work", required: true }
    - { key: open-questions, name: "Open Questions", required: true }
    - { key: update-triggers, name: "Update Triggers", required: true }
---

# Theme: {{title}}

## Definition

<!-- Define the cross-cutting organizing frame in 2-4 sentences. -->

## Why It Matters

<!-- Explain what project-level decisions or syntheses become clearer when this theme is explicit. -->

## Boundaries

<!-- State what belongs inside this theme and what should remain a concept, question, hypothesis, task, mechanism, discussion, interpretation, or story. -->

## Current Project Links

<!-- Link the questions, hypotheses, reports, child projects, concepts, methods, and tasks currently organized by this theme. -->

## Guardrails

<!-- Record constraints that should prevent over-generalization, layer mixing, causal overclaiming, or source-method confusion. -->

## Downstream Work

<!-- List task groups, analyses, child-project follow-ups, or synthesis passes motivated by this theme. -->

## Open Questions

<!-- Name unresolved questions that would change how this theme is used. -->

## Update Triggers

<!-- State what kind of new evidence, project restructuring, or completed work should cause this theme to be reviewed. -->

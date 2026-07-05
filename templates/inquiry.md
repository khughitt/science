---
id: "inquiry:{{nn}}-{{slug}}"
kind: "inquiry"
title: "{{title}}"
status: "active"
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
target: ""
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "inquiry" }
    title: { from: title }
    status: { from: status }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
    target: { default: "" }
  sections:
    - { key: summary, name: "Summary", required: true }
    - { key: variables, name: "Variables", required: true }
    - { key: data-flow, name: "Data Flow", required: true }
    - { key: assumptions, name: "Assumptions", required: true }
    - { key: unknowns, name: "Unknowns", required: true }
    - { key: parameters, name: "Parameters", required: true }
---

# Inquiry: {{title}}

## Summary

<!-- Short description of what this inquiry investigates. -->

## Variables

### Boundary In (Givens)

| Variable | Type | Provenance |
|---|---|---|
<!-- one row per given variable -->

### Boundary Out (Produces)

| Variable | Type | Validation |
|---|---|---|
<!-- one row per produced variable -->

### Interior

| Variable | Type | Notes |
|---|---|---|
<!-- one row per interior variable -->

## Data Flow

<!-- edge list describing how variables flow through the inquiry -->

## Assumptions

| Assumption | Evidence |
|---|---|
<!-- one row per assumption -->

## Unknowns

| Unknown | Notes |
|---|---|
<!-- one row per unknown -->

## Parameters

| Parameter | Value | Source | References | Note |
|---|---|---|---|---|
<!-- one row per parameter -->


---
id: "inquiry:{{slug}}"
type: "inquiry"
title: "{{label}}"
status: "{{status}}"
source_refs: []
related: []
created: "{{created}}"
updated: "{{created}}"
target: "{{target_id}}"
---

# Inquiry: {{label}}

## Summary

{{description}}

## Variables

### Boundary In (Givens)

| Variable | Type | Provenance |
|---|---|---|
{{boundary_in_rows}}

### Boundary Out (Produces)

| Variable | Type | Validation |
|---|---|---|
{{boundary_out_rows}}

### Interior

| Variable | Type | Notes |
|---|---|---|
{{interior_rows}}

## Data Flow

{{edge_list}}

## Assumptions

| Assumption | Evidence |
|---|---|
{{assumption_rows}}

## Unknowns

| Unknown | Notes |
|---|---|
{{unknown_rows}}

## Parameters

| Parameter | Value | Source | References | Note |
|---|---|---|---|---|
{{param_rows}}

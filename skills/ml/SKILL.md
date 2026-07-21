---
name: ml
description: Use when embedding, manifold, or unsupervised-structure output needs QA. Routes to the ML QA leaves.
provenance: internal
---

# Machine-Learning QA Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when the object under scrutiny is a learned embedding or unsupervised structure,
before any leaf.

## Scope boundary

Covers QA of embeddings/manifolds/clusterings regardless of source domain. Excludes assay-level
measurement QA (see `../bio/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `embeddings-manifold-qa.md` | UMAP/HDBSCAN/Mapper/CKA structure claims, cluster stability | raw-assay QA |

## Decision / compose order

Single leaf; load it directly.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../bio/SKILL.md`, `../statistics/SKILL.md`

## Success test

An embedding/clustering claim routes to the leaf with no methodology read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.

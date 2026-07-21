---
name: proteomics
description: Use when a proteomics or protein sequence/structure dataset needs measurement QA. Routes to the proteomics leaves.
provenance: internal
---

# Proteomics Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when the data is protein-level (abundance or sequence/structure), before any leaf.

## Scope boundary

Covers mass-spec proteomics QA and protein sequence/structure dataset QA. Excludes nucleic-acid
assays and embedding QA.

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `proteomics-qa.md` | MS intensity/abundance matrices, TMT/LFQ, phosphoproteomics | sequence/structure-only tasks |
| `protein-sequence-structure-qa.md` | UniProt/Pfam/CATH/Foldseek/PLM sequence or structure sets | abundance quantification |

## Decision / compose order

Leaves are independent; load whichever matches the data modality.

## Parent & neighbors

- Parent index: `../../INDEX.md`
- Neighboring routers: `../genomics/SKILL.md`, `../transcriptomics/SKILL.md`

## Success test

A proteomics dataset routes to the correct leaf with no methodology read from this router.

## Companion Skills

- `../../INDEX.md` — the skill index.

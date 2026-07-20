---
name: research-citation-discipline
description: Use when authoring or validating citations, source pointers, and bibliography references in project documents.
archetype: normative-reference
provenance: internal
---

# Citation Contract

Answers: what must a citation or source pointer mean and contain?

## Scope

Governs every citation, bibliography key, and source pointer in project prose
and entity frontmatter. It does not govern document structure or templates
(see [`../science-scientific-writing/SKILL.md`](../science-scientific-writing/SKILL.md)),
nor the annotation-token vocabulary, which is owned by
`docs/conventions/annotation-tokens.md`.

## Vocabulary / schema

| Form | Where | Means |
|---|---|---|
| `[@AuthorYear]` | prose | inline citation; the key must resolve in `papers/references.bib` |
| `[@Smith2020; @Jones2021]` | prose | multiple sources for one claim |
| `[@Smith2020, p. 42]` | prose | citation with locator |
| `Smith et al. [@Smith2020]` | prose | narrative citation |
| `cite:AuthorYear` | `source_refs` frontmatter | bibliography backing |
| `paper:AuthorYear` | `source_refs` frontmatter | link to a project paper note |

## Invariants

- Every BibTeX key used in a document has a corresponding entry in `papers/references.bib`. Creating a citation means adding the entry.
- `cite:AuthorYear` backs a bibliography entry; `paper:AuthorYear` links a project paper note. They are not interchangeable.
- Every factual claim carries either a citation or the annotation token that correctly describes its unsourced state, per [`../../docs/conventions/annotation-tokens.md`](../../docs/conventions/annotation-tokens.md). Unmarked and unsourced is not a permitted state. Which token is *appropriate* is decided by that document, not here — `[SPECULATION]`, for instance, marks author conjecture, which is not a factual claim awaiting a source at all.
- Primary sources are preferred over secondary summaries.
- Claims drawn from model knowledge are cross-checked via web search before they are committed.

## Conformance rules

Conformance is checked by `validate.sh` and `science refs check`, which resolve
every `[@Key]` against `papers/references.bib` and report unresolved keys.
`[UNVERIFIED]` and `[MISSING_CITATION]` are counted as warnings by default;
`[SPECULATION]` and `[INACCESSIBLE]` are reported as info unless `--strict`.

## Examples

- Inline: `[@Smith2020]`
- Multiple: `[@Smith2020; @Jones2021]`
- With page: `[@Smith2020, p. 42]`
- Narrative: `Smith et al. [@Smith2020] found that...`
- Frontmatter: `source_refs: ["cite:Smith2020"]`

## Versioning / migration

This leaf supersedes the citation rules formerly duplicated in
`research/SKILL.md` ("Citation Discipline") and `writing/SKILL.md` ("Citation
Format"), extracted and merged 2026-07-20. Neither router states citation rules
any longer; both link here.

## Invalid cases

1. `[@Smith2020]` with no matching entry in `papers/references.bib` — the key must resolve.
2. `paper:Smith2020` in `source_refs` where only a bibliography entry exists — use `cite:` unless a project paper note exists.
3. An unsourced factual claim carrying **no annotation token at all** — silence is not a permitted state. See [`../../docs/conventions/annotation-tokens.md`](../../docs/conventions/annotation-tokens.md) for which token applies.
4. A factual claim marked `[SPECULATION]` — that token designates author conjecture, so using it on a claim that is awaiting a source misreports what the claim is. Use the token the canonical convention assigns to that state.
5. A citation to a source read only at abstract level, presented as backing a specific numerical result.

## Success test

Is there an explicit conformance check against the vocabulary/invariants — mechanical (lint/validate) where available, an itemized checklist otherwise?

## Companion Skills

- [`literature-evaluation.md`](literature-evaluation.md) - how sources are selected and assessed before they are cited.
- [`../science-scientific-writing/SKILL.md`](../science-scientific-writing/SKILL.md) - document structure, hedging, and annotation-token usage in prose.
- [`../INDEX.md`](../INDEX.md) — the skill index.

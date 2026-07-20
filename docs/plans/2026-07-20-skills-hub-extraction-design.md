# Skills Hub Extraction (Phase 2) — Design

**Status:** approved for implementation planning, 2026-07-20.

**Scope:** the coupled `skills/research/` + `skills/writing/` hub pair.
Phase 1 (multi-axis taxonomy, templates, `archetype:` backfill and ERROR
ratchet) shipped at `1feb088c`. Phase 3 (corpus reorganization and renaming)
remains deferred — subject is derived from path, so reorganizing before the
corpus is classified means re-litigating classification during path churn.

## Goal

Restore the router invariant — *a router carries no methodology; teaching
content belongs in a typed leaf* — for the two hubs whose extraction the
`practice-guide` template-eligibility argument depends on, and deduplicate the
doctrine they currently share.

## Why these two hubs, and why together

`docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md` records six hubs. This
phase takes two, because they cannot be separated: `research/SKILL.md` and
`writing/SKILL.md` state the same doctrine in three places.

| Overlap | `research/SKILL.md` | `writing/SKILL.md` |
|---|---|---|
| Citation format and source pointers | "Citation Discipline", L161–168 | "Citation Format", L64–73 |
| Project awareness before writing | "Project Awareness", L170–180 | "Connecting to the Project", L75–87 |
| Annotation-token vocabulary | — | "Annotation Tokens", L51–62, restating `docs/conventions/annotation-tokens.md` |

Extracting either hub alone would carry these forward as duplicated leaves.
This phase is therefore a deduplication as much as an extraction.

The remaining four hubs (`data/`, `data/expression/`, `pipelines/`, and the
`statistics/` tighten-don't-extract pass) are deferred. They form a separate
subject cluster with their own unexamined overlaps.

## Extractions

### `skills/writing/SKILL.md` → nav-only router

The router's `name:` changes `scientific-writing` → `writing`. The
`scientific-writing` identifier transfers to the extracted leaf, which is the
correct breaking migration: the leaf keeps the public behavioral name and
`writing` becomes the subject router. See *Codex companion surface* below —
this rename is load-bearing there.

| Source sections | Destination | Archetype |
|---|---|---|
| Voice and Tone; Hedging Guide; Document Structure; Formatting Conventions; Length Guidelines; Connecting to the Project (merged with `research/`'s Project Awareness); Template Usage (moved from `research/`) | **`skills/writing/scientific-writing.md`** (new) | `practice-guide` |
| Annotation Tokens | collapses to a pointer at `docs/conventions/annotation-tokens.md` | — |
| Citation Format | merges into `research/citation-discipline.md` | — |

`Template Usage` lands here, not in the citation leaf: reading and complying
with the applicable document template is part of the writing workflow. The
citation leaf owns only citation and source-pointer meaning and conformance.
Splitting it the other way would leave template structure duplicated across
both leaves.

After extraction the router has one leaf of its own plus a cross-directory
companion link to `../research/citation-discipline.md`. A one-leaf router is
thin, but the directory is a real subject with named future leaves
(pre-registration prose, results-interpretation, paper-summary), and
collapsing it now would make the path decision that phase 3 owns.

### `skills/research/SKILL.md` → nav-only router

| Source sections | Destination | Archetype |
|---|---|---|
| Source Hierarchy; Confidence Calibration; Cross-Checking Key Facts; Evaluating Sources; Synthesis, Not Just Summarization | **`skills/research/literature-evaluation.md`** (new) | `practice-guide` |
| Citation Discipline, plus `writing/`'s Citation Format | **`skills/research/citation-discipline.md`** (new) | `normative-reference` |
| Working with Hypotheses; Recognizing Unmigrated Projects; Using Dashboard Summaries | **`skills/research/proposition-graph-reasoning.md`** (new) | `analysis-discipline` |
| Evidence Classification | extends existing **`skills/research/proposition-schema.md`** | `normative-reference` |
| Annotation and Curation (L121–128) | becomes an ordinary router-table row | — |

"Annotation and Curation" is routing content, but it is currently a prose
section. It converts to a row in the router's leaf table rather than being
retained as prose — a router that keeps prose sections re-acquires the hub
smell even when the prose only routes.

#### Naming: `proposition-graph-reasoning.md`

The three bundled sections share one trigger: reasoning about or updating *the
project's own* proposition graph, as distinct from evaluating external
literature. `hypothesis-discipline` would understate that. The name also pairs
with the existing `proposition-schema.md` — schema is the normative contract,
reasoning is the discipline applied to it.

Dashboard summaries are a **conditional evidence input** within this leaf,
gated on `knowledge/graph.trig` existing — not a standalone leaf. Its own leaf
would have no independent task or output; leaving it in the router would
violate the navigation-only invariant.

Template-slot fit is direct rather than forced:

- "call out that the project still needs migration work when that affects
  interpretation quality" → **Halt / escalation**
- "prefer support / dispute / unresolved language over premature verdicts" →
  **Permitted reporting language**
- "every important proposition should be falsifiable — specify what evidence
  would lower confidence" → **Required reasoning / check / precommitment**

#### Evidence classification: transfer the distinction, not the list

`research/SKILL.md` L106–119 lists the evidence categories in the `_evidence`
suffixed form. That is the **authoring alias** form, not the canonical
vocabulary. `science/model/src/science_model/reasoning.py:125–131` defines the
canonical normalized tokens without the suffix:

`empirical_data` · `benchmark` · `simulation` · `literature` ·
`expert_judgment` · `negative_result`

The suffixed variants are accepted and stripped by
`canonical_evidence_type_token`. `negative_result` is a valid-but-unranked
compatibility member with documented semantic caveats
(`reasoning.py:120–124`; `docs/user-guide/evidence-lines.md:35–43`).

The extension to `proposition-schema.md` must preserve that
canonical-vs-alias distinction and the `negative_result` caveat. Copying the
hub's list verbatim would enshrine authoring aliases as canon inside a
normative-reference — the precise inverse of that leaf's contract.

## Migration surface

The extraction is incoherent unless all of the following move with it.

### Retarget methodology-owning links

These currently point at `SKILL.md` while claiming the target contains
substantive conventions. They would still *resolve* after extraction, but
would point at nav-only routers. Retarget each to the leaf that now owns the
named methodology:

- `skills/research/proposition-schema.md:9–11` — points at `SKILL.md` for
  "source hierarchy, evaluating sources, citation discipline"
- `skills/research/annotation-curation-qa.md:111` — same-directory link
  (`SKILL.md`), claims "research-methodology and citation-discipline
  conventions"
- `skills/data/sources/openalex.md:145` — note the depth is `../../research/`,
  not `../research/`
- `skills/data/sources/pubmed.md:126` — same depth as openalex
- `skills/research/research-package-rendering.md:82` — points at
  `../writing/SKILL.md` for "narrative and citation conventions"

Three of these name **two** methodologies that now live in **different**
leaves, so they split into two links each rather than being repointed at one:

| Reference | "citation discipline" → | "project awareness" / "narrative" → |
|---|---|---|
| `openalex.md:145`, `pubmed.md:126` | `../../research/citation-discipline.md` | `../../writing/scientific-writing.md` |
| `research-package-rendering.md:82` | `./citation-discipline.md` | `../writing/scientific-writing.md` |

Links that reference a router *as a router* are correct as-is and must not be
churned — verified for `skills/data/SKILL.md:187–188` and
`skills/statistics/SKILL.md:155–159`.

### Codex companion surface

`codex-skills/` is a git-tracked generated mirror guarded by
`test_committed_codex_skills_match_fresh_generation`. Three changes are
required in `science/src/science_tool/codex_skills.py`, and none is optional:

1. **Companion source mapping** (`codex_skills.py:17–21`). The entry
   `CompanionSkill("scientific-writing", Path("skills/writing/SKILL.md"))`
   must become `Path("skills/writing/scientific-writing.md")`. Generation
   asserts `source_name == companion.canonical_name` and raises `ValueError`
   on mismatch (`codex_skills.py:163–165`), so the router rename does not
   degrade the companion — it breaks generation outright.

2. **Resource duplication** (`codex_skills.py:173–176`). Resources are copied
   by globbing `source_path.parent/*.md` and skipping the literal filename
   `SKILL.md`. With the source at `writing/scientific-writing.md`, the source
   file matches its own glob and is copied as a duplicate resource beside
   itself. The skip condition must become "skip the source file itself."

3. **Cross-directory leaf links** (`_rewrite_companion_body_links`,
   `codex_skills.py:200–212`). The rewriter matches only
   `\.\./([a-z0-9-]+)/SKILL\.md`. It has no arm for cross-directory *leaf*
   links, so `scientific-writing.md`'s link to
   `../research/citation-discipline.md` would pass through unrewritten and
   dangle in the generated tree. Leaf links into a companion directory must
   resolve to that bundled companion — here
   `../science-research-methodology/citation-discipline.md`, since
   `citation-discipline.md` is copied as a resource of the research companion.
   Leaf links into a non-companion directory follow the existing
   `../../skills/<dir>/<leaf>.md` convention.

`science/tests/test_codex_skills.py:82–99` asserts the current source paths and
link forms and must be updated in step.

### Index and doctrine

- `skills/INDEX.md` gains four leaf entries; the `scientific-writing` entry
  remaps from `skills/writing/SKILL.md` to `skills/writing/scientific-writing.md`.
- `skills/meta/skill-taxonomy.md` — record that the router invariant is now
  satisfied for `research/` and `writing/`, and that four hubs remain.
- `docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md` — update the
  router-state column for both hubs, the archetype tally, and the
  extraction-candidate list.

## Acceptance

1. `science skills lint` exits 0. All four new leaves declare `archetype:`;
   neither router declares one (routers and `INDEX.md` must not — structural
   role stays derived).
2. Both routers conform to the router profile: no methodology, no prose
   sections beyond the profile's own headings, and a `## Success test`.
3. `cd science && uv run --frozen pytest` green, including
   `test_committed_codex_skills_match_fresh_generation` against a freshly
   regenerated mirror.
4. No dangling links: every retargeted reference resolves, in both `skills/`
   and the generated `codex-skills/` tree.
5. Corpus count moves 34 → 38 classified leaves; `practice-guide` moves from
   1 (a force-fit) to 3, with `literature-evaluation` and `scientific-writing`
   as the two exemplars the eligibility rule named.

## Explicitly out of scope

- The four remaining hubs (`data/`, `data/expression/`, `pipelines/`,
  `statistics/`).
- Any directory reorganization or path rename beyond the
  `scientific-writing` identifier transfer — that is phase 3.
- Re-opening the `research-package-rendering` force-fit. Its trip-wire in
  `skills/meta/skill-authoring.md` stands; the practice-guide eligibility
  argument closes on the two extractions above, never on that leaf.

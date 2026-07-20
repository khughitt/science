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
`writing/SKILL.md` state the same doctrine in two places.

| Research ↔ writing overlap | `research/SKILL.md` | `writing/SKILL.md` |
|---|---|---|
| Citation format and source pointers | "Citation Discipline", L161–168 | "Citation Format", L64–73 |
| Project awareness before writing | "Project Awareness", L170–180 | "Connecting to the Project", L75–87 |

Separately, `writing/SKILL.md` duplicates a canonical document rather than a
sibling hub: "Annotation Tokens", L51–62, restates the four-token vocabulary
already owned normatively by `docs/conventions/annotation-tokens.md`. That is a
skill↔canonical-doc duplication, not a hub↔hub one, and it resolves by pointer
rather than by extraction.

Extracting either hub alone would carry the two shared sections forward as
duplicated leaves. This phase is therefore a deduplication as much as an
extraction.

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
| Annotation Tokens | collapses to a pointer at `docs/conventions/annotation-tokens.md`, **placed in `scientific-writing.md`** | — |
| Citation Format | merges into `research/citation-discipline.md` | — |

`Template Usage` lands here, not in the citation leaf: reading and complying
with the applicable document template is part of the writing workflow. The
citation leaf owns only citation and source-pointer meaning and conformance.
Splitting it the other way would leave template structure duplicated across
both leaves.

The annotation-token pointer belongs in `scientific-writing.md` rather than the
router, so an agent that loads the leaf directly — the normal case, since the
leaf carries the `scientific-writing` name — still learns that the four-token
vocabulary exists and where `docs/conventions/annotation-tokens.md` owns it.

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

Public names (frontmatter `name:`), following the existing
`research-<leaf>` convention set by `research-proposition-schema` and
`research-annotation-curation-qa`:

| File | `name:` |
|---|---|
| `research/literature-evaluation.md` | `research-literature-evaluation` |
| `research/citation-discipline.md` | `research-citation-discipline` |
| `research/proposition-graph-reasoning.md` | `research-proposition-graph-reasoning` |
| `writing/scientific-writing.md` | `scientific-writing` (transferred from the router) |
| `writing/SKILL.md` | `writing` |

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

#### Outcome contract (decided, not delegated)

Outcomes are **non-exclusive flagged conditions**, not a ladder and not a
verdict. Any number may hold at once. Each licenses a *prioritization* action;
none licenses a claim about how well-supported a proposition is.

| Condition | Fires when | Licenses |
|---|---|---|
| `migration-limited` | hypothesis prose carries the reasoning; scalar `confidence` is doing the epistemic work; propositions are not decomposed; evidence is not attached as support/dispute | prefer creating or refining propositions over editing prose; state that interpretation quality is bounded by migration state |
| `contested` | support and dispute lines both bear on the proposition | read the disagreement before summarizing; do not report a direction of effect as settled |
| `single-source-fragile` | support traces to one source, or to lines sharing an `independence_group` | treat support as fragile; prioritize independent replication |
| `lacks-empirical-support` | support is present but no `empirical_data` line bears on it | name the evidence kind when reporting; prioritize empirical work |
| `high-uncertainty` | the proposition sits in a neighborhood the dashboard reports as high-uncertainty | prioritize reading, replication, or model cleanup here |

**No flagged condition is not certification.** This is the load-bearing rule of
the leaf. The dashboard reports only over what has been *recorded*; silence is
equally consistent with adequate support and with nothing having been entered.
An instrument that cannot distinguish those two states cannot certify either,
so the absence of a signal licenses proceeding — and nothing more. It must
never be written up as adequate, sufficient, or well-supported.

That reasoning is this repo's standing doctrine on silent instruments, not a
local judgment: a check that cannot fail carries no information. The earlier
`InstrumentResult` work exists precisely because instruments were reporting
confident emptiness over absent inputs.

There is deliberately **no `adequate` outcome.** Nothing in the source material
establishes that the absence of dashboard warnings certifies support, and
introducing one would convert a prioritization instrument into a completeness
proof.

**Unevaluated is a distinct state.** Dashboard summaries are conditional on
`knowledge/graph.trig` existing. When it does not, the last four conditions
cannot be evaluated at all, and that must be recorded as unevaluated — never
collapsed into "no flagged condition." `migration-limited` is assessable from
the entity files alone and remains available.

Template-slot fit for the remaining slots is direct rather than forced:

- "call out that the project still needs migration work when that affects
  interpretation quality" → **Halt / escalation**
- "prefer support / dispute / unresolved language over premature verdicts" →
  **Permitted reporting language**
- "every important proposition should be falsifiable — specify what evidence
  would lower confidence" → **Required reasoning / check / precommitment**

#### Evidence classification: transfer the distinction, not the list

`research/SKILL.md` L106–119 lists the evidence categories in the `_evidence`
suffixed form. That is the **authoring alias** form, not the canonical
vocabulary. `science/model/src/science_model/reasoning.py:134–139` defines the
canonical normalized tokens without the suffix:

`empirical_data` · `benchmark` · `simulation` · `literature` ·
`expert_judgment` · `negative_result`

The suffixed variants are accepted and stripped by
`canonical_evidence_type_token`; the canonical/alias relationship is explained
in `docs/user-guide/evidence-lines.md:57–62`. `negative_result` is a
valid-but-unranked compatibility member (`reasoning.py:129`) whose semantic
caveat — it is usually better understood as a result pattern, with the line's
stance, role, and scope carrying the meaning — is at
`docs/user-guide/evidence-lines.md:53–55`.

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

**All five** name two methodologies that now live in **different** leaves, so
each splits into two links rather than being repointed at one. Destinations are
fixed here so the implementation plan cannot guess:

| Reference | Link A | Link B |
|---|---|---|
| `proposition-schema.md:9–11` ("source hierarchy, evaluating sources" + "citation discipline") | `./literature-evaluation.md` | `./citation-discipline.md` |
| `annotation-curation-qa.md:111` ("research-methodology" + "citation-discipline") | `./literature-evaluation.md` | `./citation-discipline.md` |
| `openalex.md:145` ("citation discipline" + "project-awareness") | `../../research/citation-discipline.md` | `../../writing/scientific-writing.md` |
| `pubmed.md:126` (same wording) | `../../research/citation-discipline.md` | `../../writing/scientific-writing.md` |
| `research-package-rendering.md:82` ("narrative" + "citation conventions") | `../writing/scientific-writing.md` | `./citation-discipline.md` |

`annotation-curation-qa.md`'s "research-methodology" resolves to
**`literature-evaluation.md`**, not the research router. It is a
`measurement-qa` leaf about extracted claims, literature-derived tables, and
LLM-assisted curation; what it draws on is source hierarchy and source
evaluation, which is that leaf's content. Pointing it at the router would
reproduce the indirection this phase removes.

Links that reference a router *as a router* are correct as-is and must not be
churned — verified for `skills/data/SKILL.md:187–188` and
`skills/statistics/SKILL.md:155–159`.

### Codex companion surface

`codex-skills/` is a git-tracked generated mirror guarded by
`test_committed_codex_skills_match_fresh_generation`. Five changes are
required in `science/src/science_tool/codex_skills.py`, and none is optional
(the fifth — command-body link rebasing — is described under the dangling-link
defect below):

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
   itself. Add `resource_path == source_path` as a second exclusion —
   **retain** the existing `SKILL.md` exclusion rather than replacing it. The
   research companion still sources `SKILL.md` and needs that skip; the two
   exclusions cover different companions.

3. **Cross-directory leaf links** (`_rewrite_companion_body_links`,
   `codex_skills.py:200–212`). The rewriter matches only
   `\.\./([a-z0-9-]+)/SKILL\.md` — no arm for cross-directory *leaf* links.
   **Classify by the emitted artifact set, not by parent directory.** A
   parent-directory model is wrong once `writing/` contains a source leaf, a
   router, and future leaves that are emitted three different ways. Resolve
   each link path against what generation actually emits:

   | Test, in order | Rewrites to |
   |---|---|
   | Path equals some companion's `source_path` | `../<companion-skill-name>/SKILL.md` — that leaf *is* the companion, emitted as its `SKILL.md` |
   | Path is included by the resource-copy predicate for some companion | `../<companion-skill-name>/<filename>` — copied verbatim beside that companion's `SKILL.md` |
   | Anything else, **including an excluded `SKILL.md`** | `../../skills/<dir>/<file>` — canonical source path |

   The third row is the one a parent-directory model gets wrong. After the
   rename, `writing/SKILL.md` is the router: it is neither the writing
   companion's source (that is `scientific-writing.md`) nor a copied resource
   (the `SKILL.md` exclusion drops it). It is emitted nowhere, so it must
   resolve to `../../skills/writing/SKILL.md`. This is not hypothetical — the
   new research router links to the writing router as a neighbor. Under a
   parent-directory model that link would rewrite to
   `../science-scientific-writing/SKILL.md`, which **resolves successfully**
   while silently pointing at the scientific-writing leaf instead of the
   router. A passing link check would not catch it.

   Deriving the predicate from the emitted set also keeps the rewriter honest
   if the exclusions change later: one definition governs both what is copied
   and what links point at.

   Regression cases are required for all three destinations, plus one for a
   link rewritten *inside a copied resource* (see change 4).

4. **Rewriting must reach copied resources.** `_rewrite_companion_body_links`
   is applied only to the companion's root body (`codex_skills.py:183`);
   resources are transferred by `shutil.copy2` (`codex_skills.py:176`) with no
   rewriting at all.

   This is a **pre-existing live defect**, not one this phase introduces.
   **Nine** links dangle in the committed mirror today. Six are copied
   companion resources, closed by rewriting resources:

   ```
   science-research-methodology/annotation-curation-qa.md   -> ../data/frictionless.md
   science-research-methodology/annotation-curation-qa.md   -> ../statistics/sensitivity-arbitration.md
   science-research-methodology/research-package-rendering.md -> ../pipelines/snakemake.md
   science-research-methodology/research-package-rendering.md -> ../writing/SKILL.md
   science-research-methodology/research-package-spec.md    -> ../data/frictionless.md
   science-research-methodology/research-package-spec.md    -> ../pipelines/snakemake.md
   ```

   `codex-skills/writing/`, `codex-skills/data/`, and `codex-skills/pipelines/`
   do not exist. The phase does not cause these; it makes them unavoidable,
   because `research-package-rendering.md`'s retarget cannot land correctly
   while resources go unrewritten. Routing copied Markdown resources through
   the same rewriting as the root body closes all six.

   The remaining **three** come from **command** bodies, which companion
   rewriting never touches:

   ```
   science-health/SKILL.md        -> ../docs/user-guide/evidence-lines.md
   science-plan-analysis/SKILL.md -> ../skills/statistics/estimator-certification.md
   science-pre-register/SKILL.md  -> ../skills/statistics/estimator-certification.md
   ```

   Command sources live at `commands/<name>.md` (depth 1) and are emitted to
   `codex-skills/science-<name>/SKILL.md` (depth 2), so every relative link in
   a command body is short by exactly one `../`. All three point outside
   `skills/` or at a non-companion leaf, so a depth rebase is correct and
   sufficient — no companion mapping applies. This is a fifth generator change,
   separate from the four companion changes above.

   Acceptance therefore checks the *whole* generated tree for dangling links,
   not only the files this phase touches.

`science/tests/test_codex_skills.py:82–99` asserts the current source paths and
link forms and must be updated in step.

### Index and doctrine

- `skills/INDEX.md` — four operations, not one:
  1. remap the existing `scientific-writing` row from
     `skills/writing/SKILL.md` to `skills/writing/scientific-writing.md`;
  2. add a `writing` row for the router at `skills/writing/SKILL.md`;
  3. add `research-literature-evaluation`, `research-citation-discipline`,
     and `research-proposition-graph-reasoning`;
  4. place the three research leaves in the section matching their subject —
     `Curation and Evidence` already holds `research-annotation-curation-qa`.
- `skills/meta/skill-taxonomy.md` — record that the router invariant is now
  satisfied for `research/` and `writing/`, and that four hubs remain.
- `skills/meta/skill-authoring.md:41` — live doctrine, currently false after
  this phase. It states "6 of 7 current `SKILL.md` files are **hubs**" and
  names `writing/SKILL.md` as "the most acute — 108 lines of doctrine routing
  to zero leaves." Both clauses change: four hubs remain, and `writing/` is no
  longer the acute case. The `Placement (pre-migration)` guidance above it
  (L36–40) still holds — this phase adds no directory. Regeneration then
  propagates the change to the Codex copy.
- `docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md` — update the
  router-state column for both hubs, the archetype tally, and the
  extraction-candidate list.

## Acceptance

1. `science skills lint` exits 0. All four new leaves declare `archetype:`;
   neither router declares one (routers and `INDEX.md` must not — structural
   role stays derived).
2. Both routers conform to the router profile: no methodology, no prose
   sections beyond the profile's own headings, and a `## Success test`.
3. **Leaf-template conformance, checked itemwise.** `science skills lint`
   validates metadata and links; it does **not** prove a leaf implements its
   archetype's slots. A prose move can pass lint while failing the typed-leaf
   goal, so each new leaf is checked by hand against
   `skills/meta/templates/<archetype>.md` — every slot present, and each
   filled with content of the kind the slot names rather than restated prose.

   The binding case is `proposition-graph-reasoning.md`. Its outcome contract
   is **decided here**, not left to implementers — see the next section.
   `Required evidence & artifacts` must name the entity or field that records
   each flagged condition; `Permitted reporting language` must state the
   support / dispute / unresolved vocabulary as permitted-vs-forbidden
   wording.

   The other three: `literature-evaluation.md` and `scientific-writing.md`
   each need a genuine **Common pitfalls** (pitfall → correction) and
   **Outputs**, neither of which exists in the hub text;
   `citation-discipline.md` needs **Invariants**, **Examples**, and
   **Invalid cases**, which the hub's bullet list does not supply.
4. `cd science && uv run --frozen pytest` green, including
   `test_committed_codex_skills_match_fresh_generation` against a freshly
   regenerated mirror.
5. `cd science && uv run ruff check` and `uv run pyright` both clean —
   `codex_skills.py` changes, so both apply. Note four pre-existing ruff
   errors in `science/tests/test_numeric_binding.py` and seven pre-existing
   pyright errors in `prose_lint.py` at base `1feb088c`, in files this phase
   does not touch; the requirement is no *new* findings.
6. No dangling links **anywhere in the generated tree**, not only in files
   this phase touches: the nine pre-existing danglers listed above must be
   gone. Verified by resolving every relative link in `codex-skills/` against
   the filesystem.
7. A link from the research router to `../writing/SKILL.md` resolves, in the
   generated tree, to the writing **router** — not to
   `science-scientific-writing/SKILL.md`. This is the case a link-existence
   check passes while being wrong, so it is asserted by destination, not by
   resolvability.
8. Corpus count moves 34 → 38 classified leaves; `practice-guide` moves from
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

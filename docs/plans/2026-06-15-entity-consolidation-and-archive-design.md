# Entity Consolidation & Archive — Design

> **Status:** SHIPPED — P1–P5 + tidy-up + G1 freeze guard + G2 curate inventory
> migration (local `main`, not pushed). See **§12** for as-built status and
> ratified deviations; §12 is authoritative where it differs from §1–§11.
> **Motivation:** keep a growing entity corpus legible to humans and to
> entity-consuming operations (big-picture, curate, grep, the KG) as projects
> accumulate hundreds of questions / interpretations / reports.
> **Series:** complements the substrate-retirement line
> (`2026-06-07-substrate-3a-entities-retirement-visibility-design.md`), which
> retires *aggregate-stub* rows; this doc addresses *authored markdown entities*.
> **Naming note:** the verb "distill" is already claimed by `science distill`
> (external-KG snapshot import; see `docs/user-guide/graph-and-derived-state.md`).
> This feature is therefore named **consolidation / archive**, never "distill".

## 1. Why this exists

Research projects accumulate entities monotonically; nothing today retires or
collapses authored markdown. Concrete evidence from `natural-systems-guide`
(2026-06-15, 719 entity ids):

- **191 interpretations**, of which ~20 are version snapshots of *one* evolving
  artifact — `interpretation:0069-h05-predictions-vs-dag-v3` … `-v12` and
  `interpretation:0079-parameter-derivation-dag-v3` … `-v12`. Each `vN` supersedes
  `vN-1`; only the latest carries live signal, yet all are equally visible to
  grep, the KG, and big-picture bundle assembly.
- **Bundle noise** in `/science:big-picture`: the H01 and H05 hypothesis bundles
  pulled in 49 and 48 interpretations respectively; synthesizers correctly
  collapsed most as "superseded intermediate snapshots", but only after paying to
  read them. The cost is real and grows every quarter.
- **Every read operation pays full corpus cost.** A `grep` for a concept returns
  the v3…v12 snapshots alongside the live one; an agent reading "all
  interpretations related to H05" wades through the same.

The goal is **compression with lossless retrieval**: collapse what is settled or
superseded into a canonical summary, hide the detail from default operations, but
keep it searchable on demand so the audit trail is never destroyed.

Important terminology: **default-visible** is not the same thing as
`status: active`. Many live entities use non-`active` statuses (`proposed`,
`supported`, `answered`, `complete`, etc.). The design filters out explicitly
hidden lifecycle states, not every status whose literal value is not `active`.

## 2. Two failure modes (they need different mechanisms)

The single phrase "too many entities" hides two distinct problems:

| Mode | Signature | Detection | Mechanism |
|---|---|---|---|
| **Superseded lineage** | `vN` replaces `vN-1`; a materialized `sci:supersedes`/`sci:amends` chain | **mechanical** — the chain already encodes it | lifecycle status + archive (Tiers 1–2) |
| **Semantic cluster** | N files that are really facets of one question/finding (e.g. the `t342`/`t344`/`t385` partition-test family) | **judgment** — needs similarity + human approval | cluster digest (Tier 3) |

Conflating them is the trap: the superseded case is safe to automate from graph
edges; the cluster case must stay human-in-the-loop.

## 3. Design principles (inherited from the substrate-retirement series)

1. **Read-only detection first, `--apply` second.** Mirror the 3a→3b rhythm: a
   classifier that *reports* consolidation candidates with surfaced evidence, and
   a separate, explicitly opt-in apply step. (The user's stated preference:
   extend curate's detection; keep apply separate.)
2. **Never brick a half-rolled project.** Status/visibility changes are additive
   and reversible; archived content is relocated, never deleted.
3. **Heuristics with surfaced evidence, not authoritative judgment.** Cluster
   proposals carry a one-line basis; a human reviews before apply acts.
4. **Lossless, retrievable.** Archived entities remain on disk and in an index;
   `--include-archived` and a new `science search --archived` command (§4)
   recover them through tool-mediated retrieval. The KG can still materialize
   them on demand. (Raw shell `grep` over the tracked tree still sees archived
   files — the hidden-from-search guarantee is scoped to tool surfaces; see the
   grep caveat in §4 Tier 2.)
5. **Single source of truth for locations.** Resolve entity homes through
   `science_tool.entities.resolve_path_policy` (see §7), never hardcode paths —
   the lesson from the big-picture v2-path bug fixed alongside this doc.

## 4. Tiered architecture (each tier independently shippable)

### Tier 1 — Lifecycle status as a first-class, read-honored filter

Extend the per-kind status vocabulary in the kind SSOT,
`science_model.profiles.core.CORE_PROFILE` (a `ProfileManifest` whose `EntityKind`
records each carry `statuses` / `default_status`; `profiles/schema.py`). The tool
layer derives `science_tool.entities._STATUS_VALUES` / `_DEFAULT_STATUS` from this
profile via `_KIND_DESCRIPTORS` (and exposes `valid_statuses()` /
`default_status()`), so the vocabulary is authored once in the profile and the tool
layer follows. The Kind Descriptor keystone (merged `f5157aac`) **retired the old
`science_model.kinds.CORE_KINDS`**; do not reintroduce it. Status additions:

- `superseded` — replaced by a newer entity; auto-derivable from `sci:supersedes`.
  **Already present** in many authored-markdown kinds (`interpretation`,
  `synthesis`/`report`, and most epistemic/report kinds carrying
  `["active", …, "superseded", …]`); **notably absent from `hypothesis`** (whose
  vocab is `proposed`/`under-investigation`/`partially-supported`/`supported`/
  `weakened`/`refuted`). Audit each kind and add `superseded` where missing —
  without it, `--auto-superseded` (§6) is silently blocked for that kind.
- `archived` — intentionally demoted from active operations (may or may not be
  superseded). **Net-new everywhere** — not currently in any kind's vocabulary.

Add a shared visibility predicate, e.g. `is_default_visible(status)`. The
required hidden set for the first slice is `archived` and `superseded`; broader
default-hiding for existing terminal states such as `retired`, `deprecated`, and
`abandoned` is an open question (§9). Do **not** implement this as
`status == "active"`: `proposed`, `supported`, `answered`, `complete`, and
similar kind-specific live statuses must remain default-visible.

**Visibility-predicate invariant.** `is_default_visible` is a pure function of the
status *string*, but the hidden set is global across kinds. This is only sound if
the hidden states (`archived`, `superseded`) are never a kind's *live* status. The
schema has **no live/terminal metadata** — `EntityKind` carries only `statuses`
and `default_status` (`profiles/schema.py`) — so there is no `live_statuses(kind)`
to intersect against. Make the invariant implementable as two concrete guards
alongside the descriptor-derived parity tests:
  1. **Hidden ≠ default:** assert no kind in `CORE_PROFILE` declares `archived` or
     `superseded` as its `default_status` (a hidden state can never be the status a
     freshly-authored entity is born with).
  2. **Explicit live-status allowlist:** maintain a small hand-curated set of
     statuses known to be live (`active`, `proposed`, `supported`, `answered`,
     `complete`, `draft`, `under-investigation`, …) and assert it is disjoint from
     the hidden set. This is the human-owned source of truth the schema lacks; new
     statuses must be classified into live-or-hidden when added.
If a future need for first-class lifecycle metadata emerges (a `terminal: bool` or
`lifecycle:` field on `EntityKind`), that supersedes the allowlist — noted as a
possible schema extension, out of scope for the first slice.

**Two filtering layers — keep them strictly separate (this is the crux).**

- **Status-hidden filtering is view/consumer-layer ONLY.** Every entity-*consuming*
  read path excludes hidden lifecycle states by default: entity listing and lookup
  helpers, big-picture resolver/bundle assembly, curate inventory, attention
  ranking, and `next-steps`. This removes the v3…v12 snapshot noise *without moving
  any file*. It must **not** happen in `MarkdownAdapter.discover` /
  `load_project_sources` — those feed graph materialization (`materialize.py` builds
  the graph from `sources.entities`), so a status filter there would strip the very
  `sci:supersedes` lineage the design depends on.
- **Source discovery (`MarkdownAdapter` / `load_project_sources`) filters on
  relocation ONLY** — it skips files physically under `entities/_archive/` (Tier 2),
  never on `status`. A status-hidden but not-yet-relocated entity is therefore still
  ingested into the KG and still feeds reference resolution; it is merely absent from
  default consumer views.

`superseded` is auto-applied by a graph pass over supersedes chains
(report-then-apply); `archived` is set only by Tier 3's apply step.

**The KG follows directly — filter at the view layer, not at ingestion.** The KG
must *not* drop hidden entities at `MarkdownAdapter.discover` time: the auto-derive
step
(§5) walks materialized `sci:supersedes` chains, and the provenance mitigation
(risk #1) relies on those chains surviving as the lineage record. If a superseded
node and its outbound edges never enter the graph, the very chain the derivation
reads — and the audit trail — vanish. Therefore hidden entities are **still
materialized into the KG** (so `sci:supersedes`/`sci:amends` edges and lineage are
preserved) but **excluded from default query views / bundle assembly**; recall is
via the view-layer `--include-archived` flag (§4 Tier 2). Discover-time exclusion
applies only once an entity is *relocated* to the archive (Tier 2), and even then
the surviving lineage is the digest/survivor plus the index row, not a silent drop.

**Lowest effort, highest noise-reduction-per-unit-work. Ship first.**

### Tier 2 — Archive tier + searchable index

Relocate archived entities to a scan-excluded location and record them in an
append-only index.

- **Location constraint (discovered while fixing big-picture):** the new
  `_collect_project_ids` and resolver scans do `rglob("*.md")` under
  `entities/`. An archive at `entities/_archive/` would therefore **still be
  collected**. Two candidate options:
  - (a) Archive root **outside** `entities/` (e.g. `archive/entities/<kind>/`),
    or
  - (b) Keep it under `entities/` but make all scans skip a reserved
    `_archive/` segment (one shared `_iter_entity_markdown` helper that filters
    `_`-prefixed path components).
  **Decision: (b), and option (a) is disqualified — not merely less tidy.** A
  sibling `archive/` tree is matched by the user's global gitignore
  (`~/.gitignore_global` ignores any path component named `archive`), and a
  root `archive/` already exists *untracked*, holding old design docs and
  `merge-backups/`. Routing archived entities there would (i) silently drop them
  from git version control — directly violating principle #4 (lossless,
  retrievable) and risk #1 (destroying provenance) — and (ii) collide with that
  existing scratch dir. The reserved segment `_archive` is **not** matched by the
  `archive` gitignore pattern, so `entities/_archive/` stays tracked. A single
  shared iterator enforces the skip in one place; it must sit at the
  source-discovery layer used by `MarkdownAdapter.discover` /
  `load_project_sources`, not only in big-picture helpers, so the relocation
  (not the status) is what removes a file from raw `entities/**/*.md` scans.
- **Reserved path contract:** `entities/_archive/` is reserved for this feature,
  and local-kind homes may not use `_archive` or any `_`-prefixed path segment
  under `entities/`. **Implementation note:** `KindCategory.RESERVED` is a *kind
  category*, not a path-reservation mechanism — it does not enforce this. The
  enforcement point is the existing local-home validator `_resolve_local_home`
  (`entities.py`), which already rejects absolute paths, `..`, non-`entities/`
  roots, and the bare `entities` root; extend it to also reject any `_`-prefixed
  path segment, fail-loud, so a local kind cannot declare such a home. The same
  `_`-prefix skip rule must live in the shared `_iter_entity_markdown` iterator, so
  the two stay in lockstep (ship a test asserting a `_`-prefixed local home is
  rejected *and* that the iterator skips `_archive/`). **Precondition audit:**
  before making `_`-prefix a hard scan-skip rule, confirm no existing entity file
  or home under `entities/` is already `_`-prefixed (one-time scan); the validator
  gate enforces it going forward.
- **Index:** append-only `entities/_archive/archive-index.jsonl` (under the
  tracked reserved tree — *not* the gitignored root `archive/`, §4/§8/§9), one row
  per archived entity: `{id, aliases, same_as, kind, title, digest_insight,
  superseded_by, cluster_id, original_path, archived_at}`. `digest_insight` is the
  one-line surviving claim, so the index is itself searchable without rehydrating
  files. **`aliases` / `same_as` are mandatory, not optional.** Normal alias
  resolution (`build_alias_map`, `sources.py`) reads `entity.aliases` off *loaded*
  entities; once the archived file is skipped its aliases vanish, so any
  archived-id resolution beyond the bare canonical id requires the index to carry
  them. Capture the entity's `aliases` (and any `same_as`/identity-cluster
  secondary ids) at archive time. If that capture is descoped, the
  `consolidates`-resolution promise (§8) must narrow explicitly to *canonical
  archived ids only* — a `consolidates` ref written as an alias would then fail.
- **Retrieval:** introduce a **new** top-level `science search --archived`
  command (none exists today — the only `search` is `science datasets search`),
  which reads the index. KG materialization / view assembly gains an
  `--include-archived` flag (§4 Tier 1).
- **Grep caveat — be honest about what "hidden from grep" can mean.**
  `entities/_archive/` is an ordinary tracked directory, so raw `rg`/`grep` over
  the repo *will* still match archived files. We cannot make archived content
  invisible to an arbitrary shell `grep` without either (a) deleting it (rejected
  — destroys provenance) or (b) shipping a repo-level ignore. So the guarantee is
  scoped to **tool-mediated retrieval**: every `science`/big-picture/curate read
  path skips `_archive/` by default (via the shared iterator), and `--archived`
  recovers it. As an optional ergonomic add, ship an `.ignore`/`.rgignore` entry
  for `entities/_archive/` so plain `rg` skips it too, with `rg --no-ignore` as
  the documented override — but the contract is the tool surface, not raw grep.

### Tier 3 — Cluster digest entity (the semantic-cluster case)

A consolidation collapses a cluster of N entities into **one canonical digest**
plus N archived originals.

- **Digest entity:** a new `report_kind` on the existing `synthesis`/`report`
  kind — e.g. `cluster-digest` — holding the surviving claims/insights and a
  `consolidates: [id, …]` frontmatter list pointing at the archived members.
  (Reusing an existing kind avoids a new prefix; the digest is itself a
  first-class, citable entity.)
- **Member demotion:** each consolidated entity gets `status: archived` +
  `consolidated_into: <digest-id>`, then is relocated per Tier 2.
- **Consumers prefer the digest:** big-picture bundle assembly and curate pull
  the digest; `--deep` descends into archived members.

### Tier 4 — Make big-picture / curate consume digests natively

Bundle assembly substitutes a digest for its archived members (one entry, not N).
This is where the compression actually pays off downstream — without it, Tiers
1–3 reduce clutter but bundles still re-expand.

## 5. Detection: extend curate (read-only)

`curate/inventory.py` already computes `CandidateSignals` per artifact and loads
emergent-threads orphans, but its current markdown inventory is legacy-root
oriented (`doc/**/*.md`, `specs/**/*.md`). First make curate consume canonical
`entities/` records through the shared entity iterator, then add a
**consolidation-candidate** detector that emits two cluster types, each with
evidence, and **takes no action**:

- **Superseded-lineage clusters** — walk materialized `sci:supersedes` /
  `sci:amends` chains; a *linear, acyclic* chain of length ≥ 2 is a candidate, the
  head is the survivor, the tail is archivable. Fully mechanical; high confidence.
  **Non-linear chains** (a node superseded by two others, re-supersession, or a
  cycle) are reported with their topology and **skipped from auto-apply** — the
  survivor is ambiguous, so these require human resolution like the semantic case.
  Only the unambiguous linear case is eligible for `--auto-superseded` (§6).
- **Semantic clusters** — group by (a) shared `related:` neighborhood overlap
  above a threshold, (b) same task family / `group:`, (c) title or embedding
  similarity. Lower confidence; evidence string records the basis. Surfaced for
  human review only.

Output: a `science curate --consolidation-candidates` report (text + JSON),
exit 0, no mutation — the decision-support surface for the apply step.

## 6. Apply: separate, opt-in, reversible

A distinct command — `science entities consolidate` (sibling of `entities
migrate` / `entities triage-aggregate`) — consumes an approved candidate and:

1. Writes the digest entity (human-authored or agent-drafted-then-approved).
2. Sets `status: archived` + `consolidated_into` / `superseded_by` on members.
3. Relocates members to the archive root and appends index rows.

Properties: per-cluster opt-in (never a bulk sweep), re-runs detection on live
state, and is reversible (un-archive restores location + status; the index row
records `original_path`). **Archived members are frozen** — read-only once
relocated; reversibility restores location + status *only*, and edits must go
through un-archive → edit → re-archive. Otherwise an in-place edit in `_archive/`
silently drifts from the index's `digest_insight`, which the recall path trusts
without rehydrating. For the pure linear superseded-lineage case (§5) an
`--auto-superseded` mode may set `status: superseded` from chains without a
digest (the survivor already is the digest); non-linear chains are never
auto-applied.

## 7. Interaction with the big-picture v2→v3 fix (shipped alongside)

The big-picture resolver/validator/knowledge-gaps were just migrated to read the
canonical `entities/<kind>/` homes via `resolve_path_policy` (previously they
read retired `doc/`+`specs/` paths and silently returned `{}` / validated zero
files). Consequences for this design:

- Archived entities **automatically** drop out of the resolver, orphan counts,
  bundle assembly, and the nonexistent-reference validator **once excluded from
  the entity scan** (Tier 2 location constraint, §4). No per-consumer change
  beyond the shared iterator for consumers that use the shared iterator.
- The shared `_iter_entity_markdown(project_root, *, include_archived=False)`
  helper proposed in Tier 2 should replace the ad-hoc `rglob`/`glob` sites the
  fix introduced and the others that scan `entities/` directly:
  `big_picture/resolver.py` (`directory.glob("*.md")`),
  `big_picture/validator.py::_collect_project_ids` (`entities_root.rglob("*.md")`),
  `big_picture/knowledge_gaps.py` (three `glob("*.md")` sites),
  `validate/checks/discussions.py` (the `entities/synthesis` `glob("*.md")` scan),
  and the `rglob`/`glob` sites in `entities.py`. It must **also** be the primitive
  used by the markdown storage adapter — `MarkdownAdapter.discover` is the
  KG/`load_project_sources` path. Centralizing the archive-skip rule only in
  big-picture is insufficient.
- **KG nuance (from §4 Tier 1):** the adapter-level skip filters *relocated*
  archived files, not merely hidden-status ones. Status-hidden-but-still-present
  entities continue to materialize so `sci:supersedes` lineage survives; they are
  hidden at the query/view layer, recoverable with `--include-archived`.

## 8. Data-model changes (summary)

- `science_model.profiles.core.CORE_PROFILE` (the kind SSOT since `f5157aac`;
  `kinds.py`/`CORE_KINDS` are deleted): add `archived` to applicable
  source-authored markdown `EntityKind.statuses`, and `superseded` to the few
  kinds still lacking it (most already have it, incl. `interpretation`). Update
  the descriptor-derived parity tests that assert `science_tool.entities`
  `_STATUS_VALUES` / `_DEFAULT_STATUS` track the profile, and add the two
  visibility guards from §4 Tier 1 (hidden ≠ `default_status`; live-status
  allowlist disjoint from the hidden set).
- `entities.py`: derives the status vocab from `_KIND_DESCRIPTORS` already (via
  `valid_statuses()` / `default_status()`); add the `is_default_visible(status)`
  visibility helper, not literal active-ness.
- **Local-kind `archived` handling.** Adding `archived` to `CORE_PROFILE` only
  covers core kinds. A project-local `EntityKind` may declare a **closed** status
  vocabulary (`statuses` set to an explicit list — `valid_statuses` returns that
  frozenset; only `statuses is None` is the open set that accepts any value). For
  such kinds, `entities consolidate` would fail validation when stamping
  `status: archived`. **Decision for the first slice:** `entities consolidate`
  *patches the local manifest* to append `archived` to a closed-vocab local kind's
  `statuses` (idempotent; logged), rather than rejecting it or silently widening at
  write time. Local kinds with an open vocab (`statuses: None`) need no change.
  **As-built (ratified, supersedes this paragraph): fail-loud, no auto-patch — see
  §12.1.** `consolidate` *refuses* a closed-vocab member lacking `archived` with an
  actionable error; auto-mutating a user's manifest mid-consolidate is the implicit
  widening this design otherwise fights.
  Local kinds are therefore **in scope**, gated on this manifest patch.
  **The visibility guards must extend to local manifests, not just `CORE_PROFILE`.**
  A local `EntityKind` can declare its own `default_status` and a closed
  `statuses` list (`valid_statuses` reads them via `_local_entity_kind`), so the
  two §4-Tier-1 guards apply at manifest-load and at consolidate-patch time: (1)
  the patch must never set `archived`/`superseded` as a local kind's
  `default_status`, and (2) every local status must be explicitly classified
  live-or-hidden. Because `is_default_visible(status)` is a pure hidden-set check,
  an unclassified local terminal status would silently stay **default-visible** —
  exactly the failure mode the guard exists to prevent. So a local status that is
  neither in the live allowlist nor the hidden set must **fail loud** (block the
  consolidate patch / manifest load), forcing the author to classify it, rather
  than warn-and-proceed. Run these checks against the loaded local manifest, not
  only the built-in profile.
- New `report_kind: cluster-digest`: add to `_VALID_SYNTHESIS_KINDS` in
  `validate/checks/discussions.py` (and the `synthesis.md` template's
  `report_kind` enum comment), since that set is the report_kind vocabulary.
- New `consolidates:` / `consolidated_into:` / `superseded_by:` frontmatter
  fields. Frontmatter is read dict-wise (`fm.get(...)`) in
  `science_model/frontmatter.py`; confirm no strict allowed-key validator rejects
  them.
  **Reference-resolution rule — mind the direction, only ONE field points at
  archived entities.**
  - `consolidates: [id, …]` lives on the **live digest** and points *at the
    archived members* (live→archived). This is the only archive-pointing field.
  - `consolidated_into: <digest-id>` lives on the **archived member** and points
    *at the live digest* (archived→live). Its target is live.
  - `superseded_by: <id>` lives on the superseded/archived member and points *at
    the survivor*, which is normally live (archived→live).

  So `consolidated_into` / `superseded_by` targets resolve through **normal**
  resolution against the live entity set — do **not** route them to the index.
  Only `consolidates` needs special handling: its targets are archived, relocated
  entities deliberately absent from the default scan, so `ReferenceResolver`
  (`graph/reference_resolution.py`, built `from_entities(entities)`) would either
  dangle them in the nonexistent-reference validator or force archived files back
  into the live graph. The rule: **resolve `consolidates` targets against
  `archive-index.jsonl`, not the live entity list** — seed the resolver / the
  nonexistent-ref validator with a *known-archived-id set* loaded from the index so
  those refs resolve as valid ("known but not live") without materializing the
  archived entity. (The reverse-direction fields, and all refs among live entities,
  continue through normal resolution unchanged.)
- `entities/_archive/archive-index.jsonl` schema (§4) — placed inside the tracked
  reserved tree (never the gitignored root `archive/`), so the index is versioned
  alongside the entities it records.
- Shared `_iter_entity_markdown` iterator honoring `_archive/` skip, used by
  `MarkdownAdapter`, entity helpers, big-picture, curate, and the discussions
  synthesis check.
- `_resolve_local_home` (`entities.py`) extended to reject any `_`-prefixed
  `entities/` path segment fail-loud, with the matching skip in the shared
  `_iter_entity_markdown` iterator, reserving `entities/_archive/` for this
  feature (not `KindCategory.RESERVED`, which is a kind category, not a
  path-reservation mechanism).

## 9. Open questions (for the author before writing-plans)

1. ~~**Archive location:**~~ **RESOLVED → `entities/_archive/` with scan-skip.** A
   sibling `archive/` tree is globally gitignored (and collides with an existing
   untracked scratch dir), so it would silently lose archived-entity git history;
   `_archive` is not matched by the `archive` ignore pattern. See §4 Tier 2.
2. **Digest kind:** new `cluster-digest` report_kind vs a dedicated
   `consolidation` entity kind. Reuse keeps the prefix surface small.
3. **Auto-supersede scope:** for *linear* chains only (§5), is setting
   `status: superseded` non-interactively safe, or report-only like everything
   else? (Non-linear chains are already report-only.)
4. **Embedding dependency:** semantic clustering by title overlap (no deps) vs
   embeddings (better recall, new dependency). Start dep-free?
5. **Hidden status set:** should `retired`, `deprecated`, and `abandoned` be
   default-hidden alongside `archived` / `superseded`, or should the first slice
   hide only the two new consolidation statuses? Note `retired` is already widely
   used and **default-visible today**, so hiding only `archived`/`superseded` in
   P1 is the no-regression choice; P1 must not accidentally fold `retired` into
   the hidden set.

## 10. Phasing (3a-style slices)

- **P1 — Tier 1 visibility predicate + consumer-layer filter** + auto-derive
  `superseded` from *linear* chains (report-then-apply). Includes `CORE_PROFILE`
  status-vocab updates (`archived`; `superseded` where missing) + the
  hidden-set-disjoint guard test, and default-hidden filtering in the entity
  consumers (listing/lookup, big-picture views, curate, attention, `next-steps`).
  KG ingestion is **not** filtered here — hidden-status entities still materialize
  so lineage survives (§4 Tier 1); only relocation (P3) removes them from
  `MarkdownAdapter` discovery. Unblocked, highest leverage.
- **P2 — curate canonical entity inventory + consolidation-candidate detector**
  (read-only, both cluster types, evidence). The decision-support surface.
- **P3 — Tier 2 archive tier** + shared iterator + index + `search --archived`.
- **P4 — `entities consolidate --apply`** (digest + demote + relocate) and Tier 4
  consumer substitution.

## 11. Risks & mitigations

- **Destroying provenance.** Mitigated: archive is relocation + index, never
  delete; the archive root `entities/_archive/` is git-**tracked** (a sibling
  `archive/` tree would have been globally gitignored, §4); reversible; superseded
  chains preserved as the lineage record because hidden entities still materialize
  into the KG and are filtered only at the view layer (§4 Tier 1, §7).
- **Index drift from in-place archive edits.** Mitigated: archived members are
  frozen/read-only; edits route through un-archive → edit → re-archive (§6), so the
  index `digest_insight` cannot silently diverge from the file.
- **Heuristic misclassification of semantic clusters.** Mitigated: read-only
  detection, surfaced evidence, per-cluster human approval before apply.
- **Hidden-but-needed entities.** Mitigated: `--include-archived` everywhere; the
  index keeps a one-line insight per archived entity so recall does not require
  rehydration.
- **Drift between archive-skip and consumers.** Mitigated: one shared iterator
  (§7), not per-call `rglob`.
- **Conflating live statuses with `active`.** Mitigated: visibility predicate
  excludes explicit hidden states; live non-`active` statuses stay visible.
- **Curate missing canonical entities.** Mitigated: P2 first migrates curate
  inventory to the canonical `entities/` iterator before adding candidate
  detection. (As-built: detector reads the graph directly; inventory migration
  deferred — see §12.3.)

## 12. As-built status & ratified deviations (2026-06-16)

Implemented across P1–P5 plus a tidy-up pass and the G1 freeze guard (local
`main`, not pushed). The four-tier architecture shipped faithfully; an audit
against §1–§11 found the deviations below, **ratified here as the intended end
state.** This section is authoritative where it differs from the design above.

**Phasing as built.** The design's P4 ("apply + Tier 4") was split into two
shipped phases: **P4** = `entities consolidate scaffold/apply` (digest + demote +
relocate); **P5** = Tier 4 big-picture digest substitution (digest-as-bridge
restoration, `cluster-digest` recognition, `cluster-digests` CLI). The five
shipped phases P1–P5 realize the four design phases.

1. **Local-kind closed-vocab → fail-loud, not manifest-patch (supersedes §8).**
   `entities consolidate` *refuses* a member whose local kind has a closed status
   vocabulary lacking `archived` (`consolidate.py::_is_consolidatable` /
   `_validate_members`), with an actionable "add 'archived' to that kind's
   statuses first" error — it does **not** auto-patch the manifest. Ratified:
   silently widening a user's manifest mid-consolidate is exactly the implicit
   mutation the rest of this design fights (Explicit > Defensive; fail early). The
   §4-Tier-1 visibility guards still apply at manifest load.

2. **`cluster_id` omitted from the archive index row (refines §4/§8).** The §4
   schema listed `cluster_id`; the shipped `ArchiveRow` instead carries
   `consolidated_into` (a pointer to the digest), which subsumes cluster identity —
   the digest *is* the cluster. `cluster_id` is intentionally not minted.

3. **G2 — curate inventory migrated to canonical `entities/` (RESOLVED 2026-06-17).**
   `curate/inventory.py` now discovers entities via the shared
   `iter_entity_markdown(entities/)` iterator and classifies them by frontmatter
   (`type` → `kind` → colon-prefixed `id` prefix) instead of by path; the legacy
   `specs/**`/`doc/**` globs, the `_DOC_KIND_BY_DIR` map, and the obsolete `spec`
   artifact class are deleted. Archived members (under `entities/_archive/`) drop
   out via the iterator; there is no status filter (a superseded-but-not-relocated
   entity stays visible for curation). `curate/inventory.py` is registered in the
   entity-scan guard's `ENTITY_SCANNERS`. This was the last consumer reading the
   retired layout. Tasks/knowledge-source/agents_md/emergent-threads surfaces and
   the `science curate inventory` JSON contract are unchanged. The shipped
   contract is covered by `science/tests/test_curate_inventory.py` and
   `science/tests/test_entity_scan_guard.py`.

4. **G3 — `--include-archived` is on `entities list` only (accepted scope vs §4
   Tier 1).** Archived-content recall is via `science search --archived` and
   `entities list --include-archived`. The design's mention of `--include-archived`
   on "KG materialization / view assembly" is narrowed to the list surface;
   re-materializing archived nodes into the live graph is not a supported recall
   mode (tombstone stubs already preserve `consolidates` edges). Revisit only if a
   concrete recall use-case appears.

5. **G1 — archived-member freeze made explicit (closes §6 / risk #2).** Editing an
   archived member was already incidentally blocked (the live scan skips
   `_archive/`, so resolution raised a bare `Entity not found`). A guard
   (`entities.py::_reject_if_archived`, called by `edit_entity` /
   `append_entity_note`) now makes the freeze an explicit, tested contract,
   failing loud with the `consolidated_into`/`superseded_by` target and an
   "unarchive first" pointer. Raw filesystem edits under `_archive/` remain out of
   scope, as with the raw-grep caveat (§4 Tier 2).

**Non-deviation worth recording.** The `redirect_refs` / `member_to_digest`
primitives are deliberately exposed (via the `cluster-digests` CLI) but **not**
wired into the resolver / knowledge-gaps: those surfaces do membership-matching
only, so a member→digest remap there is a provable no-op (Explicit > Defensive).
One latent fragility: resolver/digests/knowledge-gaps load per-kind via
`glob("entities/<kind>/*.md")` rather than the shared `iter_entity_markdown`; safe
today only because archived files relocate to the sibling `entities/_archive/`,
which a per-kind glob never sees. If archiving ever became in-place, these would
re-expose members — cheap insurance would be a layout-assertion test.

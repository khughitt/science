# Entity Consolidation & Archive — Design

> **Status:** proposed design, pre-implementation. Feeds the writing-plans step.
> **Motivation:** keep a growing entity corpus legible to humans and to
> entity-consuming operations (big-picture, curate, grep, the KG) as projects
> accumulate hundreds of questions / interpretations / reports.
> **Series:** complements the substrate-retirement line
> (`2026-06-07-substrate-3a-entities-retirement-visibility-design.md`), which
> retires *aggregate-stub* rows; this doc addresses *authored markdown entities*.
> **Naming note:** the verb "distill" is already claimed by
> `science distill` (external-KG snapshot import, `2026-03-04-distill-import-design.md`).
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
   `--include-archived` / `science search --archived` recovers them. The KG can
   still materialize them on demand.
5. **Single source of truth for locations.** Resolve entity homes through
   `science_tool.entities.resolve_path_policy` (see §7), never hardcode paths —
   the lesson from the big-picture v2-path bug fixed alongside this doc.

## 4. Tiered architecture (each tier independently shippable)

### Tier 1 — Lifecycle status as a first-class, read-honored filter

Extend the per-kind status vocabulary (`science_tool.entities`,
`_STATUS_VALUES` / `default_status`) with two terminal states:

- `superseded` — replaced by a newer entity; auto-derivable from `sci:supersedes`.
- `archived` — intentionally demoted from active operations (may or may not be
  superseded).

Make **every entity-consuming read path exclude non-active by default**:
big-picture resolver/bundle assembly, curate inventory, attention ranking,
`next-steps`. This alone removes the v3…v12 snapshot noise *without moving any
file*. `superseded` is auto-applied by a graph pass over supersedes chains
(report-then-apply); `archived` is set only by Tier 3's apply step.

**Lowest effort, highest noise-reduction-per-unit-work. Ship first.**

### Tier 2 — Archive tier + searchable index

Relocate archived entities to a scan-excluded location and record them in an
append-only index.

- **Location constraint (discovered while fixing big-picture):** the new
  `_collect_project_ids` and resolver scans do `rglob("*.md")` under
  `entities/`. An archive at `entities/_archive/` would therefore **still be
  collected**. Two clean options:
  - (a) Archive root **outside** `entities/` (e.g. `archive/entities/<kind>/`),
    or
  - (b) Keep it under `entities/` but make all scans skip a reserved
    `_archive/` segment (one shared `_iter_entity_markdown` helper that filters
    `_`-prefixed path components).
  Recommendation: **(b)** — keeps everything under `entities/`, and a single
  shared iterator (replacing the ad-hoc `rglob` calls the big-picture fix
  introduced) enforces the skip in one place.
- **Index:** append-only `archive/archive-index.jsonl`, one row per archived
  entity: `{id, kind, title, digest_insight, superseded_by, cluster_id,
  original_path, archived_at}`. `digest_insight` is the one-line surviving claim,
  so the index is itself searchable without rehydrating files.
- **Retrieval:** `science search --archived` reads the index; default search and
  grep see nothing. KG materialization gains an `--include-archived` flag.

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
emergent-threads orphans. Add a **consolidation-candidate** detector that emits
two cluster types, each with evidence, and **takes no action**:

- **Superseded-lineage clusters** — walk materialized `sci:supersedes` /
  `sci:amends` chains; a chain of length ≥ 2 is a candidate, the head is the
  survivor, the tail is archivable. Fully mechanical; high confidence.
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
records `original_path`). For the pure superseded-lineage case an
`--auto-superseded` mode may set `status: superseded` from chains without a
digest (the survivor already is the digest).

## 7. Interaction with the big-picture v2→v3 fix (shipped alongside)

The big-picture resolver/validator/knowledge-gaps were just migrated to read the
canonical `entities/<kind>/` homes via `resolve_path_policy` (previously they
read retired `doc/`+`specs/` paths and silently returned `{}` / validated zero
files). Consequences for this design:

- Archived entities **automatically** drop out of the resolver, orphan counts,
  bundle assembly, and the nonexistent-reference validator **once excluded from
  the entity scan** (Tier 2 location constraint, §4). No per-consumer change
  beyond the shared iterator.
- The shared `_iter_entity_markdown(project_root, *, include_archived=False)`
  helper proposed in Tier 2 should replace the three ad-hoc `rglob`/`glob` sites
  the fix introduced (`resolver._load_entities` callers, `validator._collect_project_ids`,
  `knowledge_gaps._load_*`), centralizing the archive-skip rule.

## 8. Data-model changes (summary)

- `entities.py`: add `superseded`, `archived` to terminal status vocab; helper to
  test "is active".
- New `report_kind: cluster-digest`; `consolidates:` / `consolidated_into:` /
  `superseded_by:` frontmatter fields.
- `archive/archive-index.jsonl` schema (§4).
- Shared `_iter_entity_markdown` iterator honoring `_archive/` skip.

## 9. Open questions (for the author before writing-plans)

1. **Archive location:** under `entities/_archive/` with scan-skip (recommended),
   or a sibling `archive/` tree? Affects KG scan-roots and git history.
2. **Digest kind:** new `cluster-digest` report_kind vs a dedicated
   `consolidation` entity kind. Reuse keeps the prefix surface small.
3. **Auto-supersede scope:** is setting `status: superseded` from graph chains
   safe to apply non-interactively, or report-only like everything else?
4. **Embedding dependency:** semantic clustering by title overlap (no deps) vs
   embeddings (better recall, new dependency). Start dep-free?

## 10. Phasing (3a-style slices)

- **P1 — Tier 1 status filter** + auto-derive `superseded` from chains
  (report-then-apply). Unblocked, highest leverage.
- **P2 — curate consolidation-candidate detector** (read-only, both cluster
  types, evidence). The decision-support surface.
- **P3 — Tier 2 archive tier** + shared iterator + index + `search --archived`.
- **P4 — `entities consolidate --apply`** (digest + demote + relocate) and Tier 4
  consumer substitution.

## 11. Risks & mitigations

- **Destroying provenance.** Mitigated: archive is relocation + index, never
  delete; reversible; superseded chains preserved as the lineage record.
- **Heuristic misclassification of semantic clusters.** Mitigated: read-only
  detection, surfaced evidence, per-cluster human approval before apply.
- **Hidden-but-needed entities.** Mitigated: `--include-archived` everywhere; the
  index keeps a one-line insight per archived entity so recall does not require
  rehydration.
- **Drift between archive-skip and consumers.** Mitigated: one shared iterator
  (§7), not per-call `rglob`.

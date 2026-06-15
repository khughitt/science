# Entity Consolidation P2 — Consolidation-Candidate Detector — Design

> **Status:** proposed design, pre-implementation. Feeds the writing-plans step.
> **Series:** P2 of the Entity Consolidation & Archive line
> (`2026-06-15-entity-consolidation-and-archive-design.md` §5/§10). Builds on
> **P1** (lifecycle-visibility predicate + consumer-layer filter +
> `science entities mark-superseded`, merged local `c26fee81`).
> **Naming note:** "consolidation / archive", never "distill" (that verb is
> claimed by `science distill`).

## 1. Goal

Ship the **read-only decision-support surface** for consolidation: a detector
that scans canonical `entities/**/*.md` and reports two kinds of
consolidation candidates, each with surfaced evidence, **taking no action**:

- **Superseded-lineage clusters** — mechanical, derived from materialized
  `sci:supersedes` chains (reuses P1 machinery).
- **Semantic clusters** — heuristic, dep-free, human-review-only: families of
  entities that are facets of one question/finding.

Output: `science curate consolidation-candidates` (text + JSON), `exit 0`, no
mutation. This is the input to the future P4 `entities consolidate --apply`
step; P2 never archives, demotes, or relocates anything.

## 2. Scope

**In scope (P2):**
- New top-level `consolidation_candidates.py` detector.
- Extract a shared supersedes-graph pass + entity-frontmatter iterator from the
  existing `consolidation.py` (behaviour-neutral refactor of P1 code).
- New `science curate consolidation-candidates` CLI subcommand (render only).
- Both cluster types; three dep-free semantic signals.

**Explicitly out of scope (deferred):**
- **Curate-inventory migration.** P2 does **not** touch `curate/inventory.py`
  or `collect_inventory`; migrating curate's legacy `doc/`+`specs/` inventory to
  canonical `entities/` is its own slice, bundled with P3's shared
  `_iter_entity_markdown` iterator. The detector therefore must **not** depend on
  `collect_inventory`.
- Archive relocation, the archive index, `search --archived` (P3).
- `entities consolidate --apply`, digest entities, Tier-4 consumer substitution
  (P4).
- Embeddings and fuzzy title-token clustering (see §4; revisited in the §7
  tuning round).

## 3. Module structure

Keep consolidation-domain logic at the top level; `curate` is only a render
surface.

- **`science_tool/consolidation.py` (existing, P1) — refactor:**
  - Extract `build_supersedes_graph(project_root) -> SupersedesGraph` holding the
    classified `linear` chains and `non_linear` components (the graph pass P1
    already performs inline in `mark_superseded`).
  - Promote the entity-frontmatter iterator (`_iter_entity_frontmatter`) to a
    shared, importable helper (e.g. `iter_entity_frontmatter`).
  - `mark_superseded` keeps its current public signature and behaviour, now
    *consuming* `build_supersedes_graph`; the apply-time filtering
    (`_supports_superseded`, skip-already-`superseded`, `to_mark`/`applied`)
    stays in `mark_superseded`, **not** in the shared pass. Behaviour-neutral,
    pinned by P1's existing `test_consolidation_mark_superseded.py`.
- **`science_tool/consolidation_candidates.py` (new) — the detector:**
  - `detect_consolidation_candidates(project_root, *, related_jaccard=0.5,
    min_cluster_size=2) -> ConsolidationCandidates` (a Pydantic model).
  - Lineage section: calls `build_supersedes_graph`; reports **all** lineage
    members unfiltered (see §5).
  - Semantic section: implements the three signals (§4) over the shared iterator;
    assembles, merges, and orders clusters deterministically.
- **`science_tool/curate/cli.py` (existing) — add subcommand:**
  - `@curate_group.command("consolidation-candidates")` with `--project-root`,
    `--format [json|text]`, `--related-jaccard`, `--min-cluster-size`. Calls the
    detector, renders, exits 0. No mutation.

*(Rejected alternative: place the detector inside `curate/`. The domain logic and
its P1 reuse live top-level; curate is one consumer surface, not the owner.)*

## 4. Report model

Pydantic, mirroring `curate/inventory.py::CurationInventory`
(`model_dump(mode="json")`):

```python
class LinearChain(BaseModel):
    survivor: str
    archivable: list[str]   # the superseded tail (everything but the survivor)
    members: list[str]      # all nodes in the chain, sorted

class NonLinearChain(BaseModel):
    nodes: list[str]
    reason: str             # "branched or cyclic supersedes chain"

class SemanticCluster(BaseModel):
    signal: str             # "structural-family" | "shared-anchor" | "related-overlap"
                            #   (merged sets join with "+", e.g. "structural-family+related-overlap")
    members: list[str]      # sorted entity ids
    evidence: str           # one-line human-readable basis (names the specific structural basis)

class SupersededLineage(BaseModel):
    linear: list[LinearChain]
    non_linear: list[NonLinearChain]

class ConsolidationCandidates(BaseModel):
    project_root: str
    superseded_lineage: SupersededLineage
    semantic_clusters: list[SemanticCluster]
    counts: dict[str, int]  # {"linear", "non_linear", "semantic"}
```

## 5. Superseded-lineage section (mechanical)

- Source of truth is the canonical machine-readable edge: a `relations:` entry
  with `predicate: "sci:supersedes"` (NOT top-level `supersedes:`, NOT
  `sci:amends`) — identical to P1.
- `build_supersedes_graph` classifies connected components exactly as P1's
  `_classify`: a **linear, acyclic** chain (every in/out-degree ≤ 1, one source,
  one sink) yields `survivor` = the in-degree-0 node and `archivable` = the
  remaining members. **Non-linear** components (branch / re-supersession / cycle)
  are reported with their topology and never proposed for action.
- **Unfiltered, by design.** The detector reports lineage members **regardless of
  default visibility and regardless of whether the member's kind declares the
  `superseded` status.** Detection is advisory; surfacing a candidate whose kind
  can't be auto-stamped is still useful to a human. The apply-time filtering
  (`_supports_superseded`, skip-already-`superseded`) stays inside
  `mark_superseded(apply=True)` — the detector and the apply path read the *same*
  graph but apply *different* downstream filters.

> **Real-corpus note (motivates the semantic section):** in `natural-systems`
> the canonical vN snapshot families
> (`…-h05-predictions-vs-dag-v3…v12`, `…-parameter-derivation-dag-v3…v12`) are
> **not** encoded as `sci:supersedes` chains (those interpretations carry
> `status: complete`, no supersedes relations). The mechanical section therefore
> **misses them**; they are caught only by the semantic signals below.

## 6. Semantic-cluster section (heuristic, human-review-only)

Operates on **default-visible entities only** (reuses P1's
`is_default_visible(status)` — there is no point clustering already-`superseded`/
`archived` entities). Three dep-free signals run **independently** (union); each
emitted cluster is tagged with its `signal` and a one-line `evidence` string.

### 6.1 Entity-reference hygiene (shared by 6.3 and 6.4)

Both ref-based signals consider only **entity references** — a ref string of the
shape `<kind>:<slug>` that resolves into the project's known entity-id set
(collected from the same iterator). This **excludes**:
- empty / missing ref lists,
- metadata- or tag-like scalars that are not `kind:slug` entity ids,
- references that do not resolve to a known entity id.

`source_refs:` **external citation anchors** (DOI / PMID / URL / bare-string
citations that are not entity ids) are **excluded from clustering in P2** — they
are much noisier than entity anchors. Their inclusion is a candidate knob for the
§7 tuning round, not a P2 default.

### 6.2 Structural family — `signal: "structural-family"`

Catches naming families like the vN snapshots. **Same-kind only.** The three
sub-bases below all emit this one signal; the `evidence` string names which fired
(`id-stem` / `group:` / `task-family`).
The three sub-bases produce **basis-namespaced** grouping keys so they never
collude by value collision; a group is any key shared by ≥ `min_cluster_size`
same-kind members. (Different bases yielding the *same* member-set still merge
later via §6.5 — that is the only place sub-bases combine.)
- **id-stem** — normalize an entity id: take the **local id part** (after the
  first `:`), strip a **leading numeric sequence prefix** (`^\d+-`), strip a
  **trailing version suffix** (`-v\d+$`); the residual is the *stem*. Key:
  `(kind, "id-stem", stem)`.
- **group** — exact `group:` value equality. Key: `(kind, "group", group)`.
- **task-family** — members sharing the same parent `task:` ref. **Prefix-shaped,
  not resolved:** any `task:`-prefixed string in `related:` counts; it is *not*
  validated against the entity-id set, because task entities live in `tasks/`
  (`tasks/active.md`, `tasks/done/**`), outside the `entities/` scan — there is no
  loaded task set to resolve against. `source_refs:` is **not** consulted for this
  sub-basis. Key: `(kind, "task-family", task_ref)` (one key per shared task ref).
  Two entities sharing a *typo'd/nonexistent* `task:` id would still cluster; this
  is acceptable for a human-reviewed surface, and adding real task-id resolution
  (loading `tasks/`) is a §7 tuning-round consideration, deliberately out of scope
  for P2.
- *Evidence* names the firing basis, e.g.
  `"id-stem 'h05-predictions-vs-dag' (kind interpretation; v3..v12; 10 members)"`
  or `"task-family task:t327 (kind interpretation; 4 members)"`.

> Cross-kind grouping is forbidden: a `question`, `hypothesis`, and
> `interpretation` that happen to share a slug stem must **not** be clustered
> together.

### 6.3 Shared anchor — `signal: "shared-anchor"`

Same-kind entities whose entity-refs (§6.1, from `related:` and resolvable
`source_refs:`) point at the **same anchor entity**. Any anchor shared by ≥
`min_cluster_size` same-kind entities yields a cluster of those entities.
- *Evidence:* `"5 interpretations all ref hypothesis:0005-parameter-namespace-normalization"`.

### 6.4 `related:` neighborhood overlap — `signal: "related-overlap"`

Build a graph whose nodes are entities and whose edges connect pairs whose
**entity-ref `related:` sets** (§6.1) have Jaccard ≥ `related_jaccard` (default
0.5). Connected components of size ≥ `min_cluster_size` are clusters.
- *Evidence:* `"related Jaccard 0.67 (e.g. 4/6 shared neighbors)"`.

### 6.5 Assembly, merge, ordering

- Clusters with **identical member-sets** (across any signals) are **merged into
  one** `SemanticCluster` whose `evidence` concatenates the per-signal bases in a
  deterministic order, and whose `signal` records the merged set (e.g.
  `"structural-family+related-overlap"`). Differing member-sets are listed separately so a
  human sees corroboration vs. divergence.
- All output lists are sorted deterministically (members lexicographically;
  clusters by `(signal, members)`). The report is a pure function of the on-disk
  corpus + thresholds — no timestamps, no randomness, no mtime dependence.

### 6.6 CLI knobs

`--related-jaccard` (default 0.5) and `--min-cluster-size` (default 2) are
exposed now so the §7 tuning round can sweep them without code changes.

## 7. Post-implementation validation + tuning round

A deliberate follow-up **phase** (documented here; **not** code-tasks in the P2
implementation plan):

1. Run `science curate consolidation-candidates --format json` across several
   **recently-active** projects (e.g. `natural-systems`, `therapeutics`, `meta`,
   plus others with high entity churn — variability between projects is the point).
2. Manually inspect output for **missed real groups** (false negatives) and
   **spurious clusters** (false positives).
3. Iterate: sweep `--related-jaccard` / `--min-cluster-size`, and reconsider the
   deferred signals (fuzzy title-token overlap, embeddings, external citation
   anchors) against what the real corpora actually need.

The expectation (per the design author) is that manual inspection will turn up
related groups that slip through the initial three signals; the heuristics adapt
to real-world needs in this round rather than being over-tuned up front.

## 8. Testing (TDD, synthetic `entities/` fixtures)

- **Lineage, linear:** reuse a P1-style chain fixture → one `LinearChain` with
  correct `survivor` (in-degree-0) and `archivable` tail.
- **Lineage, non-linear:** branched/cyclic fixture → reported under `non_linear`
  with topology, never elsewhere.
- **Lineage reports unsupported/statusless kinds:** a chain whose members are a
  kind lacking the `superseded` status (or a project-local kind) is still fully
  reported by the detector, even though `mark_superseded(apply=True)` would skip
  those members. (Asserts the §5 detector/apply filter split.)
- **id-stem clusters within a kind:** `interpretation:0001-foo-v1..v3` → one
  `id-stem` cluster, stem `foo`.
- **id-stem does NOT cross kinds:** `question:0001-foo`, `hypothesis:0002-foo`,
  `interpretation:0003-foo` (same stem, different kinds) → **no** cluster.
- **shared-anchor:** 3 same-kind interpretations whose `related:` all reference
  one `hypothesis:` → one `shared-anchor` cluster.
- **related-overlap threshold:** entities with `related:` Jaccard above τ cluster;
  a pair below τ does not.
- **related-overlap ignores generic/non-entity refs:** `related:` entries that
  are empty, tag-like scalars, or unresolved non-entity strings do **not**
  contribute to overlap (no spurious cluster).
- **semantic clusters exclude non-default-visible entities:** an entity with
  `status: superseded`/`archived` is omitted from semantic clustering (but a
  superseded entity still appears in the lineage section).
- **duplicate member-sets merge evidence deterministically:** a member-set
  produced by two signals yields exactly one merged `SemanticCluster` with a
  stable, concatenated `evidence`.
- **determinism:** full-report JSON snapshot is stable across runs.
- **CLI read-only:** `curate consolidation-candidates --format json|text` exits 0
  and leaves all `entities/**/*.md` mtimes unchanged.
- **P1 regression:** `mark_superseded` behaviour unchanged after the refactor
  (existing P1 suite stays green).

## 9. Data-model / dependencies

- **No new frontmatter fields, no profile/vocabulary changes.** P2 is pure read
  + report; it consumes existing `relations:`/`related:`/`source_refs:`/`group:`/
  `status:` fields.
- Reuses P1: `is_default_visible` (visibility filter), the supersedes-graph pass,
  and the entity iterator — all from `consolidation.py` / `entities.py`.
- New dependency surface: none (dep-free by §2). Pydantic + Click already in use.

## 10. Risks & mitigations

- **Mechanical section misses unencoded lineage** (real, §5 note). Mitigated:
  the semantic signals (id-stem especially) cover the vN families; the §7 round
  validates coverage on real corpora.
- **Generic over-clustering** (everything links to a hub entity). Mitigated:
  entity-ref hygiene (§6.1), same-kind constraint, external citations excluded,
  thresholds tunable in §7.
- **Cross-kind false families.** Mitigated: id-stem and shared-anchor are
  strictly same-kind, with explicit tests.
- **Hidden migration creep.** Mitigated: §2 forbids any `collect_inventory`
  dependency; the detector reads `entities/` directly via the shared iterator.
- **Non-determinism breaking snapshot tests.** Mitigated: total ordering, no
  time/random inputs, mtime-unchanged assertion.

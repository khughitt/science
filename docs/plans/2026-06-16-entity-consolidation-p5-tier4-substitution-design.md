# Entity Consolidation P5 — Tier 4 Consumer Substitution — Design

> **Status:** proposed design, pre-implementation. Feeds the writing-plans step.
> **Series:** the final tier of the consolidation/archive line
> (`2026-06-15-entity-consolidation-and-archive-design.md`, §4 Tier 4). P1 (lifecycle
> visibility) · P2 (candidate detector) · P3 (archive tier) · P4 (`entities
> consolidate`, the Tier 3 digest mutator) are all shipped and merged to local `main`.
> **Naming note:** "consolidation / archive", never "distill".

## 1. Why this exists — and what P3+P4 already achieved

Tier 4 is "make big-picture consume digests natively: substitute the one digest
for its N archived members (1 entry, not N), with `--deep` descending into the
members" (umbrella design §4 Tier 4). The motivating noise was the H05 hypothesis
bundle pulling in ~48 interpretations, ~20 of which were `vN` snapshots of one
artifact.

A crucial precondition discovered while scoping P5: **most of the literal
"substitution" is already structural after P3+P4.**

- P3 *relocates* consolidated members to `entities/_archive/` and the shared
  `entity_scan.iter_entity_markdown` skips that subtree by default, so the members
  are **already gone** from every default consumer scan.
- P4's digest is a live `synthesis` entity (`report_kind: cluster-digest`), so it
  is **already present** wherever syntheses are read.

So the remaining Tier-4 gap is narrower and more precise than "substitute". The
two big-picture *programmatic* surfaces — `big_picture/resolver.py` (question→
hypothesis association) and `big_picture/knowledge_gaps.py` (topic-coverage gaps)
— have three concrete deficiencies:

1. **Lost transitive bridges.** `resolve_questions` never emits interpretations or
   syntheses as output rows; they act *only* as transitive bridges (an
   interpretation whose `related:` lists both a question and a hypothesis links
   them at confidence `0.5`). When a cluster of interpretations is consolidated and
   archived, the bridges they provided are **silently dropped** — the members
   vanish from the scan and any `related:` ref to them simply dangles and is
   ignored. The digest that replaces them is a `synthesis`, which neither surface
   loads, so nothing restores the bridge.
2. **No recognition.** No consumer reads `report_kind: cluster-digest` or its
   `sci:consolidates` members, so a digest cannot be *labeled* as standing for N
   archived entities, and nothing can substitute it for them or descend into them.
3. **No descent path.** There is no opt-in way to expand a digest into its archived
   members (the `--include-archived` deep-read deferred from P3).

`curate/inventory.py` is **out of scope**: it scans `doc/**` and `specs/**`, never
`entities/`, so it never sees digests or members (verified). The `consolidation-
candidates` detector is **out of scope** by explicit decision (§2).

## 2. Scope — locked decisions

All five via `AskUserQuestion` this session:

| Decision | Choice |
|---|---|
| Consumer surfaces | **big-picture programmatic only**: `resolver.py` + `knowledge_gaps.py` (+ their CLI). NOT the `consolidation-candidates` detector; NOT a standalone digest CLI. |
| `--deep` descent source | **Index-only** — `ArchiveRow` fields (`id`/`kind`/`title`/`digest_insight`). No rehydration of `_archive/*.md`. |
| Default-mode behavior | **Recognition/labeling** of the digest (consumers detect `cluster-digest` and surface it as consolidating N members). Substitution itself is already done by relocation. |
| Resolver bridge model | **Both** — digest-as-bridge *and* redirect dangling member refs (the view-layer analogue of P3's graph tombstone redirect). |
| Deferred cleanups | **None** — strictly Tier 4. (`paper:` related-overlap exclusion and idempotent `apply` resume stay deferred.) |

**Forced by the data model:** index-only descent is the only option that works —
`ArchiveRow` has **no `related` field**, so a member's bridging edges cannot be
reconstructed from the index. A digest's bridging must therefore come from the
digest's *own authored* `related:`, which is the natural authoring act when you
write a cluster-digest summarizing a family.

## 3. Architecture

Three components, each independently testable. No data-model or schema change; no
new entity kind, status, or frontmatter field (P4 already added everything).

### 3.1 New `big_picture/digests.py` — the shared digest-awareness leaf

A small module (mirrors `layout.py`/`frontmatter.py` as a big-picture leaf) that
reads digests and the archive index and exposes pure helpers. It imports the P4
SSOT constants to avoid drift:

```python
from science_tool.consolidate import (
    CONSOLIDATES_PREDICATE,      # "sci:consolidates"
    CLUSTER_DIGEST_REPORT_KIND,  # "cluster-digest"
    SYNTHESIS_KIND,              # "synthesis"
)
from science_tool.archive import load_archive_index, ArchiveRow
from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.big_picture.layout import entity_dir
from science_tool.entities import is_default_visible
```

(No import cycle: `archive.py` already imports `big_picture.frontmatter`, a leaf
that imports only `yaml`/`pathlib`; `digests.py` → `consolidate`/`archive` →
`big_picture.frontmatter` is acyclic.)

```python
@dataclass(frozen=True)
class MemberSummary:
    """Index-only view of one archived, consolidated member."""
    id: str
    kind: str | None
    title: str | None
    digest_insight: str | None
    archived: bool   # True if present+active in the archive index

@dataclass(frozen=True)
class ClusterDigest:
    id: str
    title: str | None
    related: list[str]            # the digest's own authored related: edges
    member_ids: list[str]         # targets of its sci:consolidates relations, in order
    member_count: int
    members: list[MemberSummary]  # populated only when deep=True; else []

def load_cluster_digests(project_root: Path, *, deep: bool = False) -> dict[str, ClusterDigest]:
    """Scan entities/synthesis/ for visible report_kind==cluster-digest entities.

    member_ids come from each digest's relations[] entries whose predicate ==
    CONSOLIDATES_PREDICATE (read from the frontmatter dict, same shape P4 writes).
    When deep=True, each member is resolved against load_archive_index(...).active_by_id
    into a MemberSummary (archived=False when the id is absent, e.g. a scaffolded-
    but-not-yet-applied digest whose members are still live)."""

def member_to_digest(project_root: Path) -> dict[str, str]:
    """member_id -> digest_id, built from the ARCHIVE INDEX (not digest relations).

    For each active ArchiveRow whose `consolidated_into` is set, map row.id ->
    consolidated_into, plus each of row.aliases / row.same_as -> consolidated_into.
    Building from the index (rather than from digest sci:consolidates relations)
    guarantees ONLY genuinely-archived members redirect: a scaffolded-but-unapplied
    digest's members are still live and absent from the index, so they resolve
    normally."""

def redirect_refs(refs: Iterable[str], remap: Mapping[str, str]) -> list[str]:
    """Rewrite each ref through `remap` (archived member id -> digest id),
    pass-through otherwise. De-dup while preserving first-seen order."""
```

`MemberSummary.kind`/`title`/`digest_insight` come straight off `ArchiveRow`
(`ArchiveRow.digest_insight` was set by P4's `apply_consolidation`).

### 3.2 `resolver.py` — digest-as-bridge + ref-redirect

`resolve_questions(project_root)` gains no new *output* shape and no new public
parameter (its output is q→h only; members never appear as rows, so neither
`--deep` nor an `include_archived` toggle changes what it returns). The change is
purely internal correctness — restore bridges lost to consolidation:

1. **Build the redirect map once:** `remap = member_to_digest(project_root)`.
2. **Normalize every `related:` read** through `redirect_refs(_as_list(fm.get("related")), remap)`
   in all three places `related:` is consumed (inverse, back-inverse, transitive).
   A live entity that still cites an archived member by id now resolves that edge
   to the digest instead of dangling. (This is a no-op when `remap` is empty, i.e.
   no consolidations have happened — fully behavior-preserving for projects that
   never consolidate.)
3. **Digest-as-bridge:** load `digests = load_cluster_digests(project_root)` and add
   a fourth contributor to the transitive pass — a digest whose (redirect-
   normalized) `related:` lists both a question `q` and a hypothesis `h` adds
   `HypothesisMatch(h, "transitive", 0.5)` to `results[q]`, exactly as an
   interpretation does. The digest thus inherits the bridging role its archived
   members used to play, **if** it is authored with the relevant `related:` edges.

`HypothesisMatch` is unchanged (no digest-provenance field) — recognition lives in
the registry surface (§3.4), not in the q→h matches.

### 3.3 `knowledge_gaps.py` — redirect on demand edges

`compute_topic_gaps` already depends on `resolve_questions` output (so it inherits
the restored bridges automatically through `_hypotheses_for`). The only local
change is to apply the same **ref-redirect** when reading questions' `related:` in
`_compute_demand` and topics' `related:` in `_compute_coverage`, so a question or
topic that cites a now-archived member resolves to the digest rather than
dangling. Build `remap = member_to_digest(project_root)` once in
`compute_topic_gaps` and thread it into both helpers.

No digest-as-*topic* logic: topics are rarely consolidated, and `TopicGap`'s
coverage/demand model (questions↔topics↔papers) has no slot for a synthesis
digest. Output shape unchanged. (If a topic itself is archived into a digest, the
redirect makes references to it resolve to the digest id, and the archived topic
correctly drops out of `_load_topics` — no gap is emitted for a consolidated
topic, which is the desired substitution.)

### 3.4 CLI — recognition registry + `--deep`

The recognition/labeling and descent that the consuming `/science:big-picture`
skill needs are surfaced through a registry on the existing big-picture CLI
group (`big_picture/cli.py`). To keep each existing command's output shape stable
(the skill parses `resolve-questions` as a flat `{qid: ...}` map), the registry is
a **new sibling subcommand** rather than a field grafted onto `resolve-questions`:

```
science big-picture cluster-digests --project-root . [--deep]
```

- Emits JSON: `{digest_id: asdict(ClusterDigest), ...}` sorted by id.
- Default: `members: []`, `member_count` set, `related`/`member_ids` populated —
  enough for the skill to **label** "synthesis:0042 — cluster-digest consolidating
  11 entities" and to substitute it for its members.
- `--deep`: each digest's `members` carries the index-only `MemberSummary` list, so
  the skill can render the one-line `digest_insight` per archived member nested
  under the digest (one entry that *expands*, never N+1 flat).

This is part of the big-picture *programmatic* surface (the in-scope choice), not
the standalone entity-level digest CLI that was explicitly out of scope. The
`resolve-questions` and `knowledge-gaps` commands keep their exact output shapes;
their internal behavior improves (restored bridges) transparently.

## 4. What is deliberately NOT changing

- **No new entity kind / status / frontmatter field.** P4 shipped `cluster-digest`,
  `archived`, `consolidates`/`consolidated_into`/`digest_insight`. P5 only *reads*
  them.
- **No graph / materialize change.** P3 already made the KG archive-aware
  (`sci:consolidates` → `sci:ArchivedEntity` tombstone). P5 is a *view-layer*
  feature, parallel to and independent of the graph layer.
- **`resolve-questions` / `knowledge-gaps` output shapes are frozen.** Only
  internal bridge restoration changes; recognition is additive via the new
  `cluster-digests` subcommand.
- **`big_picture/validator.py` is untouched.** `_collect_project_ids` uses
  `iter_entity_markdown` without `include_archived`; digests already validate as
  ordinary syntheses and members are correctly absent. (Validator archive-awareness
  is a possible future follow-up, out of scope here.)

## 5. Edge cases & failure modes

- **No consolidations yet** (`archive-index.jsonl` absent or no `consolidated_into`
  rows): `member_to_digest` returns `{}`, `redirect_refs` is identity,
  `load_cluster_digests` returns `{}` (no `cluster-digest` syntheses). Every
  surface is byte-for-byte behavior-preserving. This is the dominant case and the
  primary regression guard.
- **Scaffolded-but-not-applied digest:** members still live, absent from the index
  → not in `member_to_digest` → not redirected, resolve normally as live entities.
  `load_cluster_digests(deep=True)` marks such members `archived=False`. No
  double-counting (the live member and the digest both present is correct here —
  consolidation hasn't been applied).
- **Member id is an alias / same_as:** `member_to_digest` seeds alias/`same_as` →
  `consolidated_into` from the `ArchiveRow`, so a `related:` ref written as an alias
  still redirects. (Mirrors `ArchiveIndex.resolvable_ids`.)
- **Digest consolidates a member that was later unarchived:** `load_archive_index`
  folds last-write-wins and drops unarchived ids from `active_by_id`, so the member
  leaves `member_to_digest` and reappears as live; `deep` marks it `archived=False`.
- **Digest with empty/malformed `relations`:** `member_ids == []`, `member_count ==
  0`; still listed in the registry (a degenerate but valid digest), no crash.
- **Two digests claim the same member:** cannot occur for *applied* members — P4's
  `apply_consolidation` fails loud on an already-archived member, so an active
  `ArchiveRow.consolidated_into` is single-valued. `member_to_digest` is therefore
  well-defined; we still assert single-ownership defensively and fail loud if the
  index ever shows two owners (parallels P3's `verify_archive`).

## 6. Testing strategy (TDD; full detail in the plan)

- `digests.py` unit: `load_cluster_digests` (default + `deep`), `member_to_digest`
  (index-built, alias seeding, scaffolded-member exclusion, unarchive drop),
  `redirect_refs` (remap, pass-through, order-preserving de-dup).
- `resolver.py`: (a) **regression** — a project with zero consolidations produces
  identical `resolve_questions` output before/after; (b) digest-as-bridge restores a
  q↔h transitive link after the bridging interpretations are consolidated into a
  digest authored with the same `related:`; (c) ref-redirect — a live entity citing
  an archived member contributes its edge via the digest.
- `knowledge_gaps.py`: demand/coverage with a redirected archived-member ref;
  archived topic drops out and emits no gap.
- `cli.py`: `cluster-digests` JSON shape default vs `--deep`; `resolve-questions`
  and `knowledge-gaps` output shapes unchanged (golden).
- Acceptance: a fixture project where consolidating an interpretation family (via
  P4 `scaffold`+`apply`) leaves big-picture seeing 1 labeled digest with N
  descendable members instead of N interpretations, and the q↔h resolution that ran
  through the family survives.

Run all tests with `PYTHONPATH=src:model/src` from the worktree's `science/` dir
using the MAIN venv pytest (the P4 `science_model`-shadowing gotcha) — though P5
touches no `science_model` file, the convention stays for safety.

## 7. Risks & mitigations

- **Silent behavior change for non-consolidating projects.** Mitigated: every new
  read path is gated on a non-empty `member_to_digest` / a present `cluster-digest`
  synthesis; the regression test pins byte-identical output when neither exists.
- **Digest authored without the bridge edges** → bridges stay lost. Accepted and
  documented: index-only descent cannot reconstruct member `related:`; restoring the
  bridge is an authoring act (relate the digest to the same q/h). The `--deep`
  registry makes the member set visible so the author can see what to relate.
- **Output-shape coupling with the big-picture skill.** Mitigated: existing command
  shapes are frozen; recognition is purely additive via a new subcommand the skill
  opts into.
- **Drift from P4 constants.** Mitigated: `digests.py` imports
  `CONSOLIDATES_PREDICATE`/`CLUSTER_DIGEST_REPORT_KIND`/`SYNTHESIS_KIND` from
  `consolidate.py` rather than re-spelling them.

## 8. Out of scope / deferred (unchanged from prior phases)

- `consolidation-candidates` detector digest-awareness; standalone
  `entities show <digest> --deep` CLI.
- `big_picture/validator.py` archive-aware member validation.
- Full rehydration of `_archive/*.md` in descent (index-only chosen).
- `paper:` kind-aware exclusion from related-overlap (P2 tuning deferral).
- Idempotent `entities consolidate apply` resume after partial multi-member failure
  (P4 deferral).

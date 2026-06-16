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
| Resolver bridge model | **digest-as-bridge** in the surfaces. `member_to_digest`/`redirect_refs` are kept as tested primitives and exposed in the registry for the `/science:big-picture` skill, but **not wired** into resolver/knowledge_gaps — there they are a provable no-op (membership matching only, never reference materialization). |
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

### 3.2 `resolver.py` — digest-as-bridge only

`resolve_questions(project_root)` gains no new output shape and no new public
parameter (its output is q→h only; members never appear as rows). The sole change
is **digest-as-bridge**: load `digests = load_cluster_digests(project_root)` and add
a fourth contributor to the transitive pass — a digest whose authored `related:`
lists both a question `q` and a hypothesis `h` adds `HypothesisMatch(h,
"transitive", 0.5)` to `results[q]`, exactly as an interpretation does. The digest
thus inherits the bridging role its archived members used to play, **if** it is
authored with the relevant `related:` edges. (No-op when no `cluster-digest`
synthesis exists — fully behavior-preserving for projects that never consolidate.)

**Ref-redirect is deliberately NOT wired into the resolver.** Tracing every branch
shows it is a provable no-op: the resolver does *membership matching* only
(`ref in questions` / `ref in hypotheses`; a bridge node listing both a q and an
h), never reference *materialization*. A `member → digest` remap rewrites an
already-unloaded archived-member id to a `synthesis` digest id, which is never a
question or hypothesis — so every branch maps an already-unmatched ref to a
still-unmatched ref, leaving the output identical. Wiring it would be dead code
(Explicit > Defensive). `member_to_digest`/`redirect_refs` live in `digests.py` as
primitives for the registry/skill (§3.1, §3.4), not for this surface. This is the
one correction to the originally-approved "Both" decision, made at plan time once
the wiring was traced concretely.

`HypothesisMatch` is unchanged (no digest-provenance field) — recognition lives in
the registry surface (§3.4), not in the q→h matches.

### 3.3 `knowledge_gaps.py` — inherits digest-awareness, no local change

`compute_topic_gaps` depends on `resolve_questions` output, so it **inherits the
restored q↔h bridges automatically** through `_hypotheses_for` — a `TopicGap`'s
`hypotheses` list reflects digest-bridged hypotheses with no local change.

A local ref-redirect in `_compute_demand` / `_compute_coverage` would be **dead
code**, and is deliberately omitted (Explicit > Defensive; avoid no-op fallbacks).
A `member → digest` remap can only change a match if a redirected id lands on a
live `topic` or `paper`, but the only consolidatable kinds are *never* topics or
papers — P4 explicitly excluded `paper`/`talk`/`book`/`bio` from the 18
consolidatable kinds, so a member id can never be in `member_to_digest` *and* be a
topic/paper id. Demand is `topic_id in question.related` (topic_id ranges over live
topics; a digest id is a `synthesis` id, never a topic id) and coverage is over
external paper ids (papers are never consolidated) — neither can be altered by the
remap. So knowledge_gaps gets correctness for free and stays byte-stable except
through the resolver it already calls.

No digest-as-*topic* logic: `TopicGap`'s coverage/demand model
(questions↔topics↔papers) has no slot for a synthesis digest. Output shape
unchanged. (If a topic itself were archived into a digest, it simply drops out of
`_load_topics` — no gap emitted for a consolidated topic, the desired
substitution; this requires no redirect because an archived topic is already absent
from the scan.)

The P5 knowledge_gaps deliverable is therefore the **inherited** correctness plus
regression/behavioral tests pinning it (§6), not new module code.

### 3.4 CLI — recognition registry + `--deep`

The recognition/labeling and descent that the consuming `/science:big-picture`
skill needs are surfaced through a registry on the existing big-picture CLI
group (`big_picture/cli.py`). To keep each existing command's output shape stable
(the skill parses `resolve-questions` as a flat `{qid: ...}` map), the registry is
a **new sibling subcommand** rather than a field grafted onto `resolve-questions`:

```
science big-picture cluster-digests --project-root . [--deep]
```

Emits a JSON object with **two** keys (frozen contract, set now before it has
consumers):

```json
{
  "digests": {
    "synthesis:0042-x": { "id": "...", "title": "...", "related": [...],
                          "member_ids": [...], "member_count": 11, "members": [...] }
  },
  "member_to_digest": {
    "interpretation:0001-old": "synthesis:0042-x",
    "0001-old-alias":         "synthesis:0042-x"
  }
}
```

- `digests`: `{digest_id: asdict(ClusterDigest), ...}` sorted by id. Default has
  `members: []` with `member_count`/`member_ids`/`related` populated — enough for
  the skill to **label** "synthesis:0042 — cluster-digest consolidating 11
  entities". `--deep` fills each digest's `members` with the index-only
  `MemberSummary` list (id/kind/title/`digest_insight`), so the skill renders one
  expandable entry per digest, never N+1 flat.
- `member_to_digest`: the explicit `member_to_digest(project_root)` map
  (**including alias / `same_as` keys**), so the skill can substitute *any*
  archived-member reference it encounters while reading raw entity files — without
  re-deriving an incomplete canonical-only map from `member_ids` (which would lose
  the alias redirects that are part of the archive-index resolution contract).

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
  identical `resolve_questions` output (the existing resolver suite is the guard);
  (b) digest-as-bridge restores a q↔h transitive link after the bridging
  interpretations are consolidated into a digest authored with the same `related:`.
  (No ref-redirect resolver test — redirect is not wired into the resolver, §3.2.)
- `knowledge_gaps.py`: a `TopicGap.hypotheses` list reflects a digest-bridged
  hypothesis (inherited from the resolver) after the bridging interpretations are
  consolidated; an archived topic drops out and emits no gap. No local-redirect
  test — there is no local redirect (§3.3).
- `cli.py`: `cluster-digests` emits both `digests` and `member_to_digest` keys;
  `digests` default vs `--deep` (`members` empty vs index-only summaries);
  `member_to_digest` includes alias keys; `resolve-questions` and `knowledge-gaps`
  output shapes unchanged (golden).
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

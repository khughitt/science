# D4 — Per-kind status-vocabulary audit

**Date:** 2026-07-12
**Status:** Complete. This is the **contract input** to the D5 implementation plan.
**Method:** four parallel read-only excavations over all 33 kinds with a declared vocabulary;
every grep hit opened and confirmed or rejected (false positives listed per kind in the raw
reports). Data census across 22 real projects / ~8,000 records.

---

## 0. The headline: there is almost nothing to excavate

D4 was commissioned on the premise that *some* per-kind vocabulary variation encodes deliberate
intent — evidenced by `test_reference_kind_does_not_gain_archived`, which pins `paper`/`book`/
`talk` as non-consolidatable. **That premise does not survive the audit.**

- The P4 design doc excludes `paper`/`book`/`talk` as **"reference kinds"** — but they are
  `EntityClass.OPERATIONAL` (`core.py:270,296,309`). The kinds that *are* `REFERENCE` —
  `topic` (`:366`), `decision` (`:464`) — **were given `archived` by the same commit.** The
  stated rationale misnames the model.
- Its other label, "authored-epistemic", is also wrong: `method`, `plan`, `search` are
  OPERATIONAL and got `archived`.
- `CONSOLIDATABLE_KINDS` in the guard test is **exactly the set of kinds that one commit
  touched**.
- The exclusion is a **3-of-13 spot-check**. Eleven further kinds also lack `archived` and are
  silently non-consolidatable; the test asserts nothing about them.
- `sci:consolidates` declares `target_kinds=[]` — **explicitly unrestricted**;
  `consolidation_candidates.py` is kind-agnostic and will cluster papers; and
  `consolidate.py:77-80` tells the operator to **go add `archived` to that kind**. The code
  treats the exclusion as *removable configuration*, not an invariant.

> **Amendment to D4.** Lifecycle **capabilities are real** — they are gated by code, not by
> data. But their **current assignment to kinds carries no recoverable intent.** Capabilities
> must therefore be **assigned by design, kind by kind**, not excavated from the existing
> lists. The lists are one commit's enumeration plus copy-paste (`synthesis`/`mechanism` and
> `finding`/`observation` are byte-identical; `discussion`/`interpretation`/`inquiry` are
> byte-identical).

---

## 1. What a capability actually is (evidence, not vocabulary)

A capability exists iff **code gates on the value**. Every gate in the toolkit:

| capability | the gate | consequence of the value being absent from a kind's vocabulary |
|---|---|---|
| **supersedable** | `consolidation.py:64-74` `_supports_superseded` | kind lands in `skipped_kinds`; `mark-superseded` can never stamp it |
| **archivable / consolidatable** | `consolidate.py:44-49` `_is_consolidatable` | `_validate_members` raises `ConsolidateError`; the kind cannot be consolidated |
| *(visibility)* | `entities.py:198` `_HIDDEN_STATUSES = {superseded, archived}` | entity stays visible on every default surface |
| *(archive sweep)* | `archive.py:22` `DEFAULT_ARCHIVE_STATUSES` | never selected for relocation |
| *(lineage invariant)* | `materialize.py:176-179` | `superseded_by:`/`resynthesized_into:` **raises `ValueError`** unless `status == "superseded"` |

**Everything else is a word.** `draftable`, `completable`, `retirable`, `deferrable` have **no
implementing code on any kind**. There is no `science entity retire`, no `complete`, no
`defer`. (`complete_task`/`defer_task`/`retire_task` are the *task* backlog — a different
system.)

**`_LIVE_STATUSES` is not a selector.** Its only readers are two guard tests. Membership in it
is bookkeeping, not behaviour.

**The graph never interprets a status.** `materialize.py:645-646` emits `sci:projectStatus` as
an **opaque literal**. The only value-level graph consumer anywhere is
`attention.py:533`, gated on `DEBT_QUESTION_STATUSES` — **question-only**.

---

## 2. The only status values that drive behaviour

Out of 45 distinct values across 33 kinds, **exactly six** are read by anything:

| value | who reads it | what breaks if it moves |
|---|---|---|
| `superseded` | `_HIDDEN_STATUSES`, `archive.py:22`, `consolidation.py:74`, `materialize.py:177` | supersession, visibility, lineage invariant |
| `archived` | `_HIDDEN_STATUSES`, `archive.py:22`, `consolidate.py:49` | consolidation gate, visibility |
| `active`, `partially-answered`, `deferred` | `DEBT_QUESTION_STATUSES` (`attention.py:27`) | **open-question debt → attention ranking** |
| `answered`, `retired`, `archived` | `_DEMAND_CLOSED_STATUSES` (`dataset_capabilities.py:40-52`) — **question/hypothesis only** | capability-coverage WARN suppression |
| `refuted` | same set (`:46`) | the *only* hypothesis-specific value read anywhere |
| `complete` | `WorkflowRunEntity.readiness()` (`entities.py:959-962`) | run readiness → **derived-dataset readiness** |

Everything else — including the whole of `proposition`'s belief axis, `hypothesis`'s
`supported`/`weakened`/`partially-supported`, `story`'s `developing`/`mature`,
`workflow-run`'s `running`/`failed` — is **read by nothing**.

**Migration hazard (D5).** `DEBT_QUESTION_STATUSES` and `_DEMAND_CLOSED_STATUSES` are
**two-axis predicates hiding in a one-axis field**. They mix lifecycle (`active`, `deferred`,
`retired`) with answeredness (`answered`, `partially-answered`). They must be **rewritten**,
never remapped:

```
DEBT_QUESTION_STATUSES   ->  status in {active, deferred} AND answer_state != answered
_DEMAND_CLOSED_STATUSES  ->  answer_state == answered OR status in {complete, retired, archived, superseded}
```

---

## 3. Dead vocabulary

**`archived`: ZERO authored entities in all 22 projects.** Exactly one `entities/_archive/`
exists (`meta/`, one row, reason `status:superseded`). The *consolidation* half — the only
writer of `status: archived` — **has never been run.** Real code, real CLI, real append-only
index; **zero production use.**

**Kinds with ZERO authored entities and no home directory:** `story`, `mechanism`,
`falsification`, `patch-definition`, `workflow-step`, `construct`, `outcome`. Their
vocabularies were authored by analogy. *An unexercised vocabulary cannot encode validated
intent* — for these, nothing constrains the answer, so nothing should be inferred from the
current lists.

**Values with zero authored uses AND zero readers:** `retired` (on all 10 reference/external
kinds), `deprecated`, `abandoned`, `amended`, `running`, `failed`, `mature`, `developing`,
`contested`, `supported`/`weakened` (proposition).

> **RULED (design rev 6): `proposition`'s three belief values are DROPPED, with no migration
> target.** Zero authored, zero readers — and the meaning they gesture at is **already owned by
> derived belief**, which `graph/belief.py` computes from evidence lines without reading `status`
> at all. So there is nothing to migrate and nothing to preserve. **`proposition` gets no domain
> axis**; its `status` becomes pure lifecycle. Rev 5 had proposed lifting them onto an authored
> `belief:` field — which would have minted a **second, hand-editable source of truth for a
> computed quantity**, and the only place in the system where an author could assert a belief the
> evidence contradicts. The collapse on `proposition` was never load-bearing; it was **vestigial**.

---

## 4. Where the collapse actively DESTROYED capability

Not merely "failed to express" — **removed**:

- **`story`** declares `draft|developing|mature` — **no terminal state at all**. So
  `consolidation.py:71` names it *by name* as skipped, and `_is_consolidatable` returns False.
  **A story cannot be superseded or consolidated because its maturity axis ate the lifecycle
  words.** Its `developing`/`mature` are read by nothing; their only CLI writer
  (`graph/cli.py:1192`) has a body that raises `_retired_writer`.
- **`hypothesis`** has exactly **one** lifecycle word (`archived`) — no `active`, no `draft`,
  no `superseded`. It cannot be superseded (`mark-superseded` skips it). This is *why* `phase`
  was invented and *why* authors wrote `status: active`.
- **`dataset`**, **`workflow`**, **`pre-registration`**, **`workflow-run`**, **`search`** lack
  `archived` and/or `superseded` → cannot be consolidated and/or superseded. `search` can be
  **archived but not superseded** — an asymmetry nothing justifies.

---

## 5. Genuine domain axes (corrections to design §7.3)

§7.3 got four kinds wrong. Corrected:

| kind | §7.3 said | AUDIT FINDS | evidence |
|---|---|---|---|
| **`dataset`** | *no domain axis* — `candidate` is a lifecycle synonym | **WRONG. `candidate` is an ACQUISITION-STATE axis.** `candidate` (not yet acquired) → `active` (acquired, has datapackage/local_path). **357 authored entities.** | `templates/dataset.md:5` defines it verbatim; `datasets_catalog.py:62,85` writes it as "catalogued but not yet acquired"; filtered at `datasets_catalog.py:536`, `dataset_prioritize.py:351,422` |
| **`paper`** | *(absent from the table)* | **MISSING ROW. A genuine reading axis**: `unread → abstract-read → read → summarized`. **41 authored files.** Declared `retired`: **0 uses.** The declared vocabulary is 100% wrong about what paper.status is for. ⚠️ **RULED (design rev 6): this row itself over-collected.** `paywalled`/`preprint`/`stub`/`background` are **NOT reading progress** — see the unbundling below. | 1857 papers: `active` 1540, `read` 21, `background` 9, `stub` 4, … `paywalled`/`preprint` were **copied from `FetchStatus`** (`paper_fetch.py:35`) — a *tool-result* status pasted onto an entity |
| **`synthesis`** | *no domain axis* | **Its real domain axis is `report_kind`** (`hypothesis-synthesis \| synthesis-rollup \| emergent-threads \| cluster-digest`) — **undeclared, dropped by `extra="ignore"`, yet branched on for CONTROL FLOW** from raw frontmatter | `consolidate.py:161` raises `ConsolidateError` on it; `big_picture/synthesis_paths.py:46`, `big_picture/cli.py:116`, `digests.py:125`; `validate/checks/discussions.py:95-120` regexes it out of raw text |
| **`plan`** | *no domain axis* | **A READINESS axis is being invented in the command layer**: `ready \| ready-with-caveats \| not-ready`. A `not-ready` plan is `active` *and* not-ready — orthogonal to lifecycle. | `commands/plan-analysis.md:102,118-121` |
| `concept`/`decision` | lifecycle synonyms (`deprecated`, `abandoned` → `retired`) | **CONFIRMED.** Zero readers, zero authored uses. | — |
| `workflow-run` | `outcome`: complete \| failed | **Half wrong.** `complete` is real (gates readiness). **`running` and `failed` are DEAD** — every consumer takes the same else-branch, so they are *indistinguishable*. `default_status="running"` is never realized (template ships `complete`; adapter defaults to `complete`). | `entities.py:959-962`; `templates/workflow-run.md:5`; `graph/storage_adapters/workflow_run.py:76` |
| `interpretation`/`discussion`/`finding`/`observation`/`evidence-line` | pure lifecycle | **CONFIRMED.** `evidence-line` **already got the split right** — its domain state (`stance`, `strength`, `independence`, `evidence_role`) is in **named fields**, and its `status` is a pure, inert lifecycle. It is the existing proof the target model works. | `evidence_lines_cli.py:19-55` |

### 5b. RULED (design rev 6): `paper.status` is FOUR axes, not two — and this audit only caught two

I recorded the `paper` finding as *"a reading/access axis"* and bundled five values into it. That
was itself a collapse — a smaller copy of the very defect the audit exists to expose. **Ruled:
only the reading progression is `reading_state`.** The rest are **inventoried and stopped**, and
the author names their axes.

| value | uses | what it actually says | disposition |
|---|---|---|---|
| `unread` / `abstract-read` / `read` / `summarized` | 21+ | **reading progress** | → **`reading_state`** (the only assignment made) |
| `paywalled` | — | **access** — can we obtain the PDF? | **ADJUDICATE.** Not reading progress. |
| `preprint` | — | **publication version** — preprint vs version of record | **ADJUDICATE.** Not reading progress. |
| `stub` | 4 | **record completeness** — placeholder, not a real summary | **ADJUDICATE.** Not reading progress. |
| `background` | 9 | **role/relevance** — why this paper is in the corpus | **ADJUDICATE.** Not reading progress. |

**The strongest evidence for the unbundling is in this audit's own evidence column, and I walked
past it:** `paywalled` and `preprint` were **copied from `FetchStatus` (`paper_fetch.py:35`)** —
they are the return codes of a *download tool*, pasted onto an entity's identity. A fetch outcome
is not a fact about the paper; it is a fact about our last attempt to get it. That alone
disqualifies them from any authored semantic axis, and it is why D5 must **stop** here rather
than assign.

**Mapping any of these four to a reading state would fabricate reading progress no author ever
claimed** — the same class of error as inventing a `verdict` for an archived hypothesis.

---

## 6. The toolkit prescribes illegal statuses — in FIVE places

The original regression (`pre-registration: committed`) was not a one-off. Command docs are an
**uncontrolled fourth status authority**:

| surface | prescribes | legal? |
|---|---|---|
| `commands/pre-register.md:258` | `status: "committed"` | was illegal — **fixed** in `e462b5f7` |
| `commands/plan-analysis.md:118-121` | `ready \| ready-with-caveats \| not-ready` | **illegal** (and a different axis entirely) |
| `commands/plan-pipeline.md:243` | `merged` | **illegal** |
| `commands/critique-approach.md:205` | `critiqued` | **illegal** — would raise a Pydantic `Literal` error on a patch-definition |
| `commands/sketch-model.md:203` | `status: sketch` on an inquiry | **illegal** — contradicts `templates/inquiry.md:5` (`active`) |

**P0 must adjudicate every command-prescribed status**, not just template-prescribed ones. The
guard shipped in `e462b5f7` covers templates only.

---

## 7. Commons: two authoritative definitions, and a LIVE CRASH

`TYPE_MIXIN_NAMES = {dataset, paper, topic, theme}` (`entity_schema/profile.py:16`).

- **`science-entity-base-1.0.json:70` declares `"status": {"type": "string"}`** — an **open
  string, no enum**. `EntityKind` declares **closed** vocabularies. **They contradict, and
  nothing reconciles them.**
- **It bites:** `~/d/science-commons/datasets/variant-labels-dbsnp-human/entity.md` carries
  **`status: exploratory` — a *code-file* status** (`code/lifecycle.py:12-19`). The open schema
  admitted it; nothing caught it.
- **No instrument can see it.** `status_vocabulary.py:57` walks `<project_root>/entities`.
  Commons stores records at `papers/<key>/entity.md`, `datasets/<slug>/entity.md` — **commons
  has no `entities/` directory.** The one check that would catch this is **structurally
  incapable of reaching commons records.** Another silent instrument.
- **LIVE CRASH — overlay merge. REACHABLE TODAY, not latent.** `overlay-1.1.json:47` permits a
  project to overlay `status`. Where `status` carries **no `science:merge` annotation**, policy
  defaults to **`REPLACE`** (`merge.py:29`), and `commons/overlay.py:286-288` **raises
  `OverlayMergeError` on `REPLACE`** — in a branch whose own comment calls it *"unreachable for
  a validated overlay."*

  | mixin | ships | declares `status`? | policy |
  |---|---|---|---|
  | `paper` / `topic` / `theme` | **1.0 and 2.0** | 2.0: `science:merge: project_only` | **PROJECT_ONLY** — safe (all records on 2.0) |
  | **`dataset`** | **1.0 ONLY — there is no 2.0** | **no** → falls through to base `{"type":"string"}`, un-annotated | **`REPLACE` → CRASH** |

  **Correction to an earlier draft of this section**, which claimed the 2.0 mixins fix this and
  all records are on 2.0. That is true for paper/topic/theme and **false for `dataset`**:
  `~/d/science-commons/datasets/variant-labels-dbsnp-human/entity.md:2` pins
  `schema_profile: science-entity-base/1.0+dataset/1.0`. **Every commons dataset is on the
  crashing path today.** Any project that overlays a commons dataset's `status` hard-fails the
  merge now. (fb-2026-07-12-006.)
- All 328 commons paper/topic/theme records are `status: active`. Not one has used any other
  value.

---

## 8. Half-wired: the vocabulary and the relation model disagree

`topic`/`decision`/`theme` declare `superseded`, and `consolidation.mark_superseded` will
auto-stamp it — **but `sci:supersedes` (`core.py:687-701`) restricts endpoints to
`workflow-run` + the six `_CONCLUSION_KINDS`, and topic/decision/theme are in neither.**
`materialize.py:1697-1725` raises `ValueError` on an out-of-pair authored relation. **So a
topic that authors the canonical supersession edge breaks `graph materialize`.** The only
working path is `superseded_by:` frontmatter, which emits `sci:supersededBy` — a predicate that
is **not a declared RelationKind** and therefore bypasses the endpoint check entirely.

---

## 9. Ambiguous migrations — D5 must REFUSE these and request adjudication

| kind | value(s) | why no mechanical rule exists |
|---|---|---|
| `hypothesis` | `phase`×`status` **contradictions**: `candidate\|retired` ×2, `active\|proposed` ×1 | the two mapping rules disagree — terminal-vs-draft. No file content resolves it. |
| `hypothesis` | `status: retired` ×2 | fb-005 ruled the *intended* fact was `weakened` (a verdict); the author wrote a workflow word. Lifecycle `retired` vs verdict `weakened` is undetermined. |
| `question` | `resolved` ×25, `partially-resolved` ×2 | genuinely ambiguous: answeredness (`answered`) **or** lifecycle (`complete`/`retired`)? |
| `interpretation` | `final` ×71 | maps to `complete` — **but natural-systems uses BOTH `final` (34) and `complete`**, so that project is drawing a distinction the schema lacks. Must confirm they are one state before collapsing. |
| `dataset` | `candidate` ×357 | **acquisition state, not draftness** (§5). Do NOT map to `draft`. |
| `pre-registration` | `complete` ×10 | did a completed pre-reg retain `commitment: committed`? **The freeze bit was overwritten and cannot be recovered from `status` alone.** |
| `plan` | `ready`/`ready-with-caveats`/`not-ready`, `merged`, `implemented`, `approved`, `agreed`, `locked` | a readiness axis and a commitment axis, both un-modelled |
| `report` | `published`, `generated`, `applied`, `review` | `applied` describes a *downstream consequence*; `generated` an *authorship* fact — different axes, not lifecycle |
| `inquiry` | all 4 entities (`sketch`/`planned`/`specified`) | the real lifecycle lives on **`patch-definition.inquiry.status`** (`InquiryStatus`, read at `store/inquiry.py:577`). **Two spellings of one axis on two kinds.** The `inquiry` *kind* looks vestigial. |
| `discussion` | `revised` ×1 | `active`, `complete`, or the successor in a supersedes chain? Nothing says. |

**Named information-loss traps** (D5 §9): an existing `status: archived` **has already
destroyed its verdict** → leave `verdict` absent and **report the loss**. Do **not** mechanically
map `disposition: closed` → `status: retired`.

---

## 10. `disposition` is inert — the strongest argument for D2

**`disposition` has ZERO authored entities across all 22 projects** (`disposition_basis`: 0
files). Therefore:

- `attention.py:136` — terminal-hypothesis exclusion from ranking — **has never fired.**
- `attention.py:538-594` `list_rehoming_debt` returns `unwired` **in every project**.
- `commands/big-picture.md:215-219` — Candidate/Retired frames — **select on a field no file
  carries.**

The machinery shipped in `d2fc4d13` is entirely inert in practice. Deleting it (D2) costs
nothing that is in use.

---

## 11. Live defects surfaced en route (not caused by the split)

1. **`ProjectEntity.readiness()` is `ready iff status == "done"`** (`entities.py:548-557`) — and
   `"done"` is in **no kind's vocabulary**. So a task `blocked_by: [plan:x]` / `[method:x]` /
   `[pre-registration:x]` / `[workflow:x]` / `[search:x]` **can never become ready.**
2. **The pre-registration freeze point is INERT.** `committed` is enforced nowhere:
   `_pre_registration_commitment_targets` (`materialize.py:1282`) and `freshness.py:159` emit
   commitment edges with **no status check** — an *uncommitted* pre-reg produces byte-identical
   graph edges to a committed one. The freeze the estimator doctrine depends on has no
   mechanism. (This is what `fb-2026-07-11-024` was reaching for.)
3. **seq-feats' 18 `status: open` questions** contribute **zero** open-question debt to
   attention ranking — invisible debt, exactly the fb-005 class.
4. **4 files committed with the literal unrendered string `status: "{{status}}"`** (2 concept,
   2 theme).
5. **`report` has no template** (`templates/report.md` does not exist), so
   `science entity create report` is impossible — all 114 reports were hand-written.
6. `commands/search-literature.md` prescribes **no frontmatter at all** — authors invent it.

---

## 12. Proposed capability set (to be ASSIGNED by design, per §0)

```
supersedable      -- gated: consolidation.py:74      [REAL, in use]
consolidatable    -- gated: consolidate.py:49        [REAL, zero production use]
draftable         -- no gate exists                  [must be BUILT or dropped]
completable       -- no gate exists                  [must be BUILT or dropped]
retirable         -- no gate exists                  [must be BUILT or dropped]
deferrable        -- no gate exists                  [must be BUILT or dropped]
```

**`entity_class` must NOT imply capabilities** — the audit confirms it does not track them
today (REFERENCE `topic`/`decision` are consolidatable; OPERATIONAL `paper`/`book`/`talk` are
not; OPERATIONAL `method`/`plan`/`search` are).

Two of the six capabilities are real and gated. **Four are words with no implementation** — so
"which kinds are draftable/completable/retirable/deferrable" is not a question the current code
can answer, and the D5 plan must either **build the gate or drop the capability**. Declaring a
capability nobody implements is how this whole class of defect started.

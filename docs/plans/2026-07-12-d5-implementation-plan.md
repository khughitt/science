# D5 — Entity Schema Convergence: Implementation Plan

> **rev 5.** Rev 1 was rejected as not executable (seven contract defects, all confirmed). Rev 2
> rebuilt it. Review then ruled two more things rev 2 had gotten wrong: the **six-field "belief
> cluster" is three unrelated ownership patterns**, and **`verdict` is an authored adjudication by
> contract** — not "authored for now" (design rev 8, rev 3 of this plan).
>
> **Rev 4 was the first revision corrected by an instrument rather than by review.** Task 1 shipped,
> ran, and **stopped the plan**: the corpus numbers were right, but the **9-repo rollout roster was
> not** — it covers **85 of 147 hypotheses (58%)**, it double-counts two symlinks, and it omits the
> one project that owns every file the belief ruling was written for. **The rev-7 mapping is
> unchanged and now certified cell-for-cell by that instrument.**
>
> **rev 5** closes four execution defects in rev 4's own correction — the shape of which is worth
> noticing, because *deriving* the roster was necessary and not sufficient:
> **(1)** Step 0 printed a report but never wrote the `roster.json` that later steps consume.
> **(2)** `before-$(basename $PWD).trig` collides — `science/meta` and `health/meta` both basename to
> `meta` and would clobber each other's graph diff. **(3)** 18 roots are only **15 git repositories**
> (`science/meta` + 3 fixtures share `~/d/science`), so commit grouping must derive from
> `git rev-parse --show-toplevel`. **(4)** Asserting `18/147` is not a gate — one root can vanish
> while another gains the same count; the gate is **exact `(root, n)` set equality** against a
> manifest snapshotted before apply and re-checked before the ratchet.
> Also ruled: the three fixture roots are **schema-contract participants** (pinned like everything
> else; unpinned-behaviour coverage moves to purpose-built temp projects, and the missing-status
> canary gets an explicit adjudication entry — **no inference shortcut for fixtures**), and
> `cancer/mechanisms/evolution` is a **hard gate** that must clear preflight before any write.
> See "What rev 3 got wrong" at the end.

> **For agentic workers:** implement task-by-task. Steps use checkbox (`- [ ]`) syntax.
> **Every task ends green.** A task that ends with a red suite is a broken task, not a slice.

**Goal:** Make one authoritative, versioned, composable JSON Schema the source of truth for a
project-authored entity kind — and migrate `hypothesis` onto it, splitting the collapsed `status`
into a lifecycle (`status`) and an epistemic conclusion (`verdict`) without fabricating a fact.

**Architecture:** Converge on the schema system that **already exists** (commons'
`entity_schema`: `schema_profile` → `allOf` → Draft 2020-12). Do **not** invent a second one.
Project kinds join via a new **base 2.0** plus a per-kind mixin. Pydantic becomes a *projection*
taken after schema validation — **never a second authority**.

**Tech stack:** Python 3.12+, Pydantic v2, `jsonschema` (Draft 2020-12), Click, `uv`, pytest, rdflib.

**Contract inputs (ruled, not proposals):**
- [`2026-07-12-authoritative-entity-schema-design.md`](2026-07-12-authoritative-entity-schema-design.md) rev 7 — **§7.3, §7.4, §8 (phasing), §9 (D1–D5), §10 rev 7.**
- [`2026-07-12-d4-status-vocabulary-audit.md`](2026-07-12-d4-status-vocabulary-audit.md).

---

## Global constraints

Apply to **every** task; not restated per-task.

1. **No "legacy"/"compatibility" layer.** No heuristic dual-read of `status`.
   **A *versioned* boundary is not a compatibility layer.** The forbidden thing is code that
   *guesses* which meaning applies. An explicit, authored version pin that *declares* it is
   exactly what D5 requires ("introduce target schema versions"). That distinction is what makes
   Task 8's per-project rollout legal — and it is the only reason it is.
2. **Never fabricate a fact.** Write only derivable values. Otherwise **refuse the file, report
   it, exit non-zero.** Traps: no mechanical `disposition: closed` → `retired`; `status: archived`
   has already destroyed its verdict (leave `verdict` **absent**, report the loss); `paper`'s
   `paywalled`/`preprint`/`stub`/`background` are **not** reading states.
3. **Fail early, no silent fallbacks. Composition over inheritance. Explicit over defensive.**
4. **No AI-attribution trailer** on commits or PRs. Use `~/d/` in docs/code.
5. **Run from the package dir** (no root `pyproject.toml`):
   `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`;
   `cd science/model && uv run --frozen pytest`.
6. **A check that only fires on downstream data MUST be run against downstream data before
   shipping.** This plan exists because a check was green in CI and broke five projects. The
   toolkit repo has **no `entities/` of its own** — green CI proves nothing here.

**Real APIs (rev 1 invented three modules that do not exist — use these):**
- `science_model.frontmatter`: `split_frontmatter(text) -> (dict, str)`, `parse_frontmatter(path)`, `render_frontmatter(fields, body)`, `atomic_write_text(path, text)`.
- `science_tool.entities`: `find_entity`, `_render_markdown`, `_atomic_replace_text`, `valid_statuses`, `default_status`.
- There is **no** `science_tool/migrations/` package, **no** `science migrate` CLI, **no** `science_tool/frontmatter.py`. Task 7 creates the migration module; register its command on `entity_group` (`cli.py:188`).

**Name collision — read before Task 5.** A `verdict/` subsystem and a `science verdict` CLI group
already exist (`src/science_tool/verdict/`): they parse `**Verdict:** [+]` polarity tokens out of
**interpretation** bodies and roll them up per claim. They **never touch hypotheses**
(`grep hypothesis src/science_tool/verdict/*.py` → nothing), so there is no functional collision —
but do **not** wire the new `hypothesis.verdict` field into that subsystem. They are different
concepts that share a word. *(Open question below: whether they should eventually be related.)*

---

## What the corpus actually says (re-measured in rev 4 by the Task 1 instrument)

**147 authored hypotheses — across 18 project roots, not 9 repos.**

> ### ⛔ rev 4 corrected the roster. Every rev through 3 carried a roster that contradicted its own total.
> Rev 1–3 said *"147 hypotheses in **9 repos**"* and then listed per-repo counts that **sum to 85**.
> Both numbers appeared in one sentence and neither was ever added up. The `147` was right (it was
> measured across all of `~/d`); the **repo list** was the uncertified artifact — and it is the one
> Task 11 would have *executed*. It covers **85 of 147 (58%)**.
>
> Two independent causes, both of which a hand-maintained list invites:
> - **`~/d/r/mm30` and `~/d/r/cbioportal` are symlinks**, into `cancer/cancer-types/multiple-myeloma`
>   and `cancer/data-sources/cbioportal`. They are not separate repos. Migrating "both" is migrating
>   one repo twice, and Task 11's graph-diff would have diffed a repo against itself.
> - **Six real projects were simply never listed**, holding **58 hypotheses** — including
>   `cancer/mechanisms/evolution`, which owns **every one of the 13 belief-cluster files** that
>   design rev 8's ruling and Task 2b's corruption fix exist to handle. The blast radius of the
>   headline defect sat entirely outside the rollout.
> - **Three of the 18 roots are fixture projects inside this toolkit's own `science/tests/`.** They
>   hold 4 hypotheses and they are *not* optional: closing the schema breaks our own suite if they
>   are not migrated with everything else.
>
> **Derive the roster; never list it.** (Same lesson as the Phase-6 import guard: *a guard that LISTS
> its scope has a hole by construction.*) The roster below is produced by globbing `science.yaml`,
> `.resolve()`-ing to collapse symlinks, and running `science entity field-inventory`.

| project | n | in rev 1–3's list? |
|---|---|---|
| `cancer/cancer-types/multiple-myeloma` *(= the `r/mm30` symlink)* | 30 | yes |
| `health/processes/post-acute-infection` | 20 | **NO** |
| `cancer/mechanisms/evolution` ← **owns all 13 belief-cluster files** | 20 | **NO** |
| `natural-systems` ← owns `0009` | 14 | yes |
| `cancer/data-sources/cbioportal` *(= the `r/cbioportal` symlink)* | 12 | yes |
| `health/comparisons/pan-disease` | 8 | **NO** |
| `science/meta` · `protein-landscape` | 7 each | yes |
| `health/meta` | 6 | yes |
| `health/processes/cycles` | 5 | **NO** |
| `seq-feats` · `health/processes/immunity` | 4 each | seq-feats only |
| `cancer/therapeutics` | 3 | yes |
| `3d-attention-bias` | 2 | yes |
| `cancer/conditions/pre-cancer` | 1 | **NO** |
| `science/tests/fixtures/{big_picture/minimal_project, spec_y_kitchen_sink, commons_mm30_canary/project}` | 2+1+1 | **NO** |
| **total** | **147** | **85** |

The `status` × `phase` cross-tab and the 36-key vocabulary below were **already measured over the
full 147** — the Task 1 instrument reproduces both cell-for-cell — so the rev-7 mapping stands
exactly as ruled. **Only the roster was wrong, and only Task 11 consumed it.**

| `status` × `phase` | n |
|---|---|
| `proposed` + `active` | **60** |
| `proposed` + `candidate` | 36 |
| `proposed` + *(absent)* | 28 |
| `weakened` + `active` | 6 |
| `supported` + *(absent)* | 4 |
| `under-investigation` + *(absent)* | 4 |
| `supported` + `active` | 2 |
| `active` + *(absent)* | 2 *(off-vocabulary)* |
| `weakened`+`candidate`, `active`+`active`, `partially-supported`+*(absent)* | 1 each |
| **`retired` + `candidate`** | **1** ← `natural-systems/0009` |
| *(no status)* | 1 ← test fixture |

**The mapping (design §10 rev 7).** `phase` **is** the lifecycle; `status` was only ever the verdict.

| source | → target |
|---|---|
| `phase: candidate` | `status: draft` |
| `phase: active` **or absent** | `status: active` |
| `status: proposed` \| `under-investigation` | **`verdict` absent** — contributes nothing to lifecycle |
| `status: supported`\|`weakened`\|`partially-supported`\|`refuted` | `verdict: <same>` |

→ **145 deterministic, 2 refused.** `disposition:` is authored on **zero of 147** — deleting it
is free.

## And what rev 1 never looked at: the FIELD vocabulary

**36 distinct authored frontmatter keys** across those 147 files:

```
147 kind, title, id, related · 146 status · 143 created, updated · 128 source_refs · 107 phase
 38 required_capabilities · 33 origins · 31 added_by · 28 lens_views · 22 ontology_terms
 17 datasets · 13 external_hypothesis_id, author_stated_evidence, evidence_stance, belief_state
 12 identification, confidence_label, confidence_mechanistic_label · 11 tags · 8 priority
  6 review_state · 3 profile, description, promoted_from, aliases · 2 role, promotion_criteria,
    domain, confidence · 1 composition_rule, capability_scope, rival_model_packet
```

**This is why strictness cannot ship in the same slice as the value migration.** Closing the
schema (`unevaluatedProperties: false`) against a mixin declaring ~15 keys would reject 20+ keys
on real files. **Declaring this vocabulary IS P0**, and P0 precedes P2m (design §8). Rev 1 skipped
it. Phase 0 below is that work.

---

## Phases

| phase | tasks | changes meaning? | ends with |
|---|---|---|---|
| **0 — Declare the fields (P0)** | 1, 2, **2b** | **No** *(2b fixes a live bug)* | every authored key given one of four dispositions; the `_authored_magnitude` chain deleted |
| **1 — Certify the mapping** | 3–4 | **No** | inventory + adjudication artifact; writes nothing |
| **2 — Schema substrate (P2)** | 5, 6, **6b**, 7 | **No** | base 2.0, core mixin, **project extensions**, D3 validator + verdict-evidence graph check — all **wired**, strict, green |
| **3 — The atomic slice (P2m)** | 8–11 | **YES** | all 18 roots migrated, graph-diffed, validate exit 0 |
| **4 — Ratchet (P3)** | 12 | No | `hypothesis` → ERROR |

**Ownership partition (design rev 8) runs through the whole plan.** A field is **core**,
**project-extension**, **renamed/migrated**, or **derived/deleted** — never "declared because we
saw it." Task 2 decides; Task 6 encodes core; **Task 6b composes project extensions**; Task 9
applies renames and deletions. Strictness (`unevaluatedProperties: false`) cannot land before 6b,
because closing the schema without project extensions would force mm30's one-project fields into
the core mixin for all 22 projects.

---

## Phase 0 — Declare the field vocabulary (P0)

### Task 1: `science entity field-inventory` — declare-or-delete

**Files:**
- Create: `science/src/science_tool/field_inventory.py`
- Modify: `science/src/science_tool/entities_cli.py`
- Test: `science/tests/test_field_inventory.py`

**Interfaces:**
- Produces: `field_inventory(project_root: Path, kind: str) -> dict[str, int]` — authored key → file count.
  Task 2 consumes it; Task 11's reconciliation gate re-runs it.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_field_inventory.py
from pathlib import Path

from science_tool.field_inventory import field_inventory


def _write(root: Path, name: str, keys: dict) -> None:
    d = root / "entities" / "hypotheses"
    d.mkdir(parents=True, exist_ok=True)
    fm = "\n".join(f'{k}: "{v}"' for k, v in keys.items())
    (d / f"{name}.md").write_text(f"---\n{fm}\n---\n\nbody\n", encoding="utf-8")


def test_counts_authored_keys_only(tmp_path: Path) -> None:
    _write(tmp_path, "0001-a", {"id": "hypothesis:0001-a", "kind": "hypothesis",
                                "title": "T", "status": "proposed", "phase": "active"})
    _write(tmp_path, "0002-b", {"id": "hypothesis:0002-b", "kind": "hypothesis",
                                "title": "T", "status": "proposed"})
    inv = field_inventory(tmp_path, "hypothesis")
    assert inv["status"] == 2
    assert inv["phase"] == 1
    # Internal/derived fields must NOT appear: this reads AUTHORED frontmatter, never the
    # enriched `raw` dict. `_enrich_raw` (sources.py:713) injects `project`, `canonical_id`,
    # `profile`, `type`, `aliases`, `content_preview` -- none of which any author wrote.
    for derived in ("project", "canonical_id", "content_preview", "aliases", "type"):
        assert derived not in inv


def test_ignores_other_kinds(tmp_path: Path) -> None:
    _write(tmp_path, "0001-a", {"id": "question:1", "kind": "question", "title": "T"})
    assert field_inventory(tmp_path, "hypothesis") == {}
```

- [ ] **Step 2: Run and fail**

```bash
cd science && uv run --frozen pytest tests/test_field_inventory.py -q
```
Expected: `ModuleNotFoundError: No module named 'science_tool.field_inventory'`

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/field_inventory.py
"""Count AUTHORED frontmatter keys per kind, across a project.

Reads the authored frontmatter -- `split_frontmatter` on the file's own bytes -- and NOT the
enriched `raw` dict the graph loader builds. `_enrich_raw` (graph/sources.py:713) injects
`kind`, `type`, `canonical_id`, `profile`, `aliases` and `content_preview` before Pydantic
ever sees the record. Inventorying THAT would declare six fields no author has ever written,
and closing a schema around them would then reject every real file.

This is the P0 "declare or delete" instrument (design §8). It must be run, and its output
adjudicated, BEFORE any schema is closed with `unevaluatedProperties: false`.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from science_model.frontmatter import split_frontmatter

from science_tool.entity_scan import iter_entity_markdown


def field_inventory(project_root: Path, kind: str) -> dict[str, int]:
    entities_root = project_root / "entities"
    if not entities_root.is_dir():
        return {}
    counts: Counter[str] = Counter()
    for path in iter_entity_markdown(entities_root):
        fm, _body = split_frontmatter(path.read_text(encoding="utf-8"))
        if fm.get("kind") != kind:
            continue
        counts.update(fm.keys())
    return dict(counts)
```

- [ ] **Step 4: Green**

```bash
cd science && uv run --frozen pytest tests/test_field_inventory.py -q
```
Expected: `2 passed`

- [ ] **Step 5: Wire a report-only CLI command** on `entity_group`, mirroring Task 3's shape
  (`--json` flag; prints `key  count`). No writes.

- [x] **Step 6: Run it across the DERIVED roster and reconcile to the 36-key list above.**
  Use Task 11 Step 0's derivation — **not** a hand-written repo list. That is what this step caught.

**If the union is not exactly those 36 keys, STOP** and update this document. The mixin in Task 6
is generated from this list, and a key missing from it becomes a hard validation failure on real
files the moment Task 6 closes the schema.

> **✅ EXECUTED 2026-07-12 — and it stopped the plan, exactly as designed.**
>
> The **36-key union reconciled exactly**, and the instrument reproduced the `status` × `phase`
> cross-tab **cell for cell** (60 / 36 / 28 / …, 88-file contradiction cohort). The rev-7 mapping is
> now certified against the corpus by the sanctioned scanner rather than an ad-hoc grep.
>
> **But the hand-written 9-repo list resolved to 85 files, not 147** — see the rev-4 correction at
> the top of this document. The step was written to reconcile the *key union*; what it actually
> caught was a bad *population*. Both numbers had been sitting in one sentence since rev 1.
>
> The instrument only found it because it was run over `~/d/**/science.yaml` rather than the list —
> i.e. **because it derived its own scope.** Had it been run over the nine repos it was told to run
> over, the union would still have been ~32 keys and might well have been waved through.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/field_inventory.py science/src/science_tool/entities_cli.py science/tests/test_field_inventory.py
git commit -m "feat(entities): field-inventory -- declare-or-delete instrument for P0"
```

---

### Task 2: Adjudicate the 36 keys — into FOUR dispositions, not one

**Not a code task — a decision task with a written artifact.** Its output is what Task 6 encodes.

> **⛔ "Observed somewhere" is NOT an admission rule for the core mixin.** Rev 2 of this plan put
> every declared corpus key into the global `mixin-hypothesis`, which **violates design §6's
> ownership contract**: a project-local field (mm30's `confidence_mechanistic_label`) would become
> a **core Science field** for all 22 projects, just because one project authored it. Ownership is
> a **scope**, and the inventory must decide scope per key.

Every key gets **exactly one** of four dispositions:

| disposition | meaning | goes where |
|---|---|---|
| **core** | a real field of *every* hypothesis | `mixin-hypothesis-1.0.json` |
| **project-extension** | real, but owned by **one project** | `extension-<project>.<name>-1.0.json`, composed via the project's declared extensions (Task 6b) |
| **rename / migrate** | real, but under the wrong name or on the wrong entity | a rename in Task 9 |
| **derived / delete** | must not be authored at all | removed by Task 9 |

**Core (25):** `id`, `kind`, `title`, `status`, `verdict`, `closure_basis`, `created`, `updated`,
`related`, `source_refs`, `origins`, `added_by`, `tags`, `ontology_terms`, `datasets`,
`description`, `aliases`, `priority`, `domain`, `role`, `lens_views`, `review_state`,
`promoted_from`, `promotion_criteria`, `rival_model_packet`, `external_hypothesis_id`,
`identification`, `superseded_by`, `resynthesized_into`, `archive_ref`.

**Core, but owned by the deferred P1 capability subsystem (3):** `required_capabilities`,
`capability_scope`, `composition_rule` — declared, not absorbed.

**Derived / delete (2):** `phase` (folds into `status`, rev 7) · `profile` (`_enrich_raw` sets it;
3 files hand-author it — strip them).

### The six-field "belief cluster" — RULED (design rev 8). It is **three unrelated ownership patterns.**

| field | files | ruling | disposition |
|---|---|---|---|
| `belief_state` | 13 | **The second-source-of-truth defect, exactly.** Hypothesis belief is **already computed** — `graph/belief.py`'s `_claims()` iterates `(Proposition, Hypothesis)` and `aggregate_belief()` processes hypothesis evidence lines. | **DELETE** |
| `evidence_stance` | 13 | **Not belief.** `literature-supported` describes **provenance/coverage**, not epistemic magnitude. | **project-extension** (`evidence_scope`), else delete. **Remove from `_authored_magnitude`.** |
| `author_stated_evidence` | 13 | **Source provenance, not current belief.** | **rename/migrate** → structured origin metadata, or project-local `source_stated_evidence`. **Must never influence computed belief.** |
| `confidence` | 2 | **Too ambiguous for a core schema** — unscoped subjective assessments. | **rename/migrate** → a project-local prior or an `expert_judgment` evidence line, else delete |
| `confidence_label`, `confidence_mechanistic_label` | 12 | **Real MM-specific interface fields, not core Science fields.** The MM exporter reads them and emits them *separately* from derived `bundle_belief`. | **project-extension** (mm30) |

- [ ] **Step 1:** Write `docs/plans/2026-07-12-hypothesis-field-adjudication.md`: for each of the
  36 keys record its file count, **every** code reader (grep, then **open every hit** — `role`,
  `datasets`, `priority`, `domain` collide with ordinary English), and its disposition.
- [ ] **Step 2:** Confirm the `evidence_stance` / `confidence` fates with the owning projects
  (mm30, cancer-evolution) — "project-extension **or** delete" is left open above **on purpose**,
  and it is the project's call, not the toolkit's.
- [ ] **Step 3:** Commit the adjudication doc.

---

### Task 2b: Delete the `_authored_magnitude` fallback chain — a LIVE bug, and a trap

> **✅ SHIPPED 2026-07-12.** Behavior-neutral on the real corpus, **proven**: `science validate` in
> `cancer/mechanisms/evolution` (which owns all 13 files) emits **zero** `belief.*` findings both
> before and after. The chain was already dead in production — see the ladder below. Full suite green
> (only the 4 pre-existing `test_feedback_cli` telemetry-window failures, which fail identically with
> these changes backed out).
>
> **It orphaned three guarantees — Task 7 Step 3c now re-homes all three on the `verdict` axis.**

**This must land BEFORE `belief_state` is removed, or removing it silently corrupts 13 hypotheses.**

`validate/checks/evidence_lines.py:395-411` walks
`("belief_state", "evidence_stance", "author_stated_evidence")` and **returns on the first
recognized token**:

```python
        for field in ("belief_state", "evidence_stance", "author_stated_evidence"):
            raw = fm.get(field)
            if not raw:
                continue
            token = str(raw).strip().lower().split()[0].split("(")[0].strip("-_:")
            if token in _AUTHORED_MAGNITUDE:
                return _AUTHORED_MAGNITUDE[token], path
```

**The corpus has 13 files with `belief_state: speculative` — and the same 13 with
`evidence_stance: literature-supported`.** Because `belief_state` is checked first, the
`evidence_stance` value has **never once reached this check**. And
`_AUTHORED_MAGNITUDE["literature-supported"] == "supported"` (line 379), while
`_AUTHORED_MAGNITUDE["speculative"] == "speculative"`.

> **So deleting `belief_state` naively promotes 13 hypotheses from the LOWEST rung
> (`speculative`) to `supported` — purely as an artifact of field order.** Nothing about the
> evidence changed. This is the same class of defect as the collapsed `status`: a value silently
> standing in for a different axis, and a consumer reading whichever one it happens to see first.

> ### And it is worse than that: the chain is ordered most-cautious → most-boastful.
> All 13 files carry **all three** fields at once, and `_MAG_INDEX` is
> `speculative=0 < fragile=1 < supported=2 < well_supported=3`:
>
> | authored | rung |
> |---|---|
> | `belief_state: speculative` | **0** — the floor |
> | `evidence_stance: literature-supported` | **2** |
> | `author_stated_evidence: established (barcoded mouse)` | **3** — the ceiling *(the parser takes the leading token)* |
>
> | you delete… | the field that then wins | result |
> |---|---|---|
> | *(nothing — today)* | `belief_state` → 0 | **every rule silent** |
> | `belief_state` | `evidence_stance` → 2 | `refutation-masked` **ERROR** possible |
> | `belief_state` + `evidence_stance` | `author_stated_evidence` → **3** | all three fire, ERROR likely |
>
> **Peeling the fields off in the obvious order walks the corpus UP the ladder — the careful fix is
> worse than the careless one.** And because every real file sits at rung 0 today, while every rule
> requires rung > 1, **the three rules currently fire on nothing.** That is what makes deleting the
> whole chain exactly behavior-neutral, and any partial fix a corruption.

**The chain is DELETED, not adapted.** `evidence_stance` and `author_stated_evidence` are
**provenance**, and provenance must never set an epistemic magnitude — that is the whole ruling.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_authored_magnitude.py
def test_provenance_fields_never_set_an_epistemic_magnitude(tmp_project) -> None:
    # `literature-supported` says WHERE the claim came from, not HOW STRONG the evidence is.
    # It must not reach the belief ladder at all -- not first, not as a fallback, never.
    write_hypothesis(tmp_project, "0001-x",
                     extra={"evidence_stance": "literature-supported"})
    assert _authored_magnitude(ctx(tmp_project), prov, claim_uri("hypothesis:0001-x")) is None


def test_author_stated_evidence_never_sets_a_magnitude(tmp_project) -> None:
    write_hypothesis(tmp_project, "0002-y", extra={"author_stated_evidence": "established"})
    assert _authored_magnitude(ctx(tmp_project), prov, claim_uri("hypothesis:0002-y")) is None
```

- [ ] **Step 2: Run and fail** — both currently return `"supported"` / `"well_supported"`.

- [ ] **Step 3: Implement.** Reduce the loop to the single authored field the check is *for*, or
  delete `_authored_magnitude` outright if `belief_state` was its only legitimate input — which
  Task 2's grep decides. **Do not** simply drop `belief_state` from the tuple and leave the other
  two: that is precisely the corruption above.

- [ ] **Step 4: Green.** Then run `science validate` in mm30 and cancer/therapeutics (the projects
  holding these 13 files) and **diff the belief-authoring findings before and after**. The count
  may change; **no hypothesis's magnitude may silently rise.**

- [ ] **Step 5: Commit.**

---

### The `verdict` contract — RULED (design rev 8)

**`hypothesis.verdict` is AUTHORED, and its semantic owner is the adjudicating author.** Not
"authored for now." Task 6's schema and Task 7's graph check both implement this contract:

1. **Absent** = *no adjudication has been recorded* (not "no evidence").
2. **Every authored verdict must have qualifying, resolvable evidence or interpretation basis at
   graph time — NOT only when `status: complete`.** A verdict with nothing behind it is a
   fabrication whatever the lifecycle says. *(Rev 2 of this plan scoped the graph check to
   `complete` only. Wrong — and it would have let a `draft` hypothesis assert `refuted` with no
   evidence at all.)*
3. **`complete` additionally requires a verdict to be present** (rev 6).
4. **Computed systems may report a recommendation or a disagreement — never populate or overwrite
   the authored verdict.** The moment they can, it stops being an adjudication.
5. **Any future deterministic rollup gets a distinct derived name.** It does not silently take over
   `verdict`'s ownership.

> **Why this is not the `belief` defect.** Hypothesis-level derived belief **already exists**
> (`_claims()` covers `SCI_NS.Hypothesis`). What does not exist is a **total, versioned mapping**
> from that belief — or from interpretation-polarity rollups — onto
> `partially-supported|supported|weakened|refuted`. **There is no derived hypothesis *verdict*.**
> Adjudication is not a rounding of a scalar: it weighs criteria, context and the hypothesis's
> composition. `belief` was a second source of truth for a quantity a policy **already computed**;
> nothing computes an adjudication.

---

## Phase 1 — Certify the mapping (report-only)

### Task 3: `science entity status-inventory`

**Files:**
- Create: `science/src/science_tool/status_inventory.py`
- Modify: `science/src/science_tool/entities_cli.py`
- Test: `science/tests/test_status_inventory.py`

**Interfaces:**
- Produces `inventory(project_root, *, adjudication: dict[str, Adjudicated] | None = None) -> StatusInventory`.
  `InventoryRow(path, entity_id, status, phase, target_status, target_verdict, target_closure_basis, ambiguity)`;
  `StatusInventory.deterministic` / `.ambiguous`. Task 7 consumes it and **adds no mapping logic of
  its own** — a rule living in the migration but not the inventory would mean the report a human
  approved is not the migration that ran.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_status_inventory.py
from pathlib import Path

import pytest

from science_tool.status_inventory import Adjudicated, inventory


def _hyp(root: Path, name: str, *, status: str | None, phase: str | None) -> None:
    d = root / "entities" / "hypotheses"
    d.mkdir(parents=True, exist_ok=True)
    lines = ["---", f'id: "hypothesis:{name}"', 'kind: "hypothesis"', 'title: "T"']
    if status is not None:
        lines.append(f'status: "{status}"')
    if phase is not None:
        lines.append(f'phase: "{phase}"')
    lines += ["---", "", "body"]
    (d / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")


def test_phase_is_the_lifecycle_status_is_the_verdict(tmp_path: Path) -> None:
    # The 60-file cohort: both template defaults. `phase` owns the lifecycle. `proposed`
    # means "the evidence has not spoken" -- which is ABSENCE, not `draft`.
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    row = inventory(tmp_path).rows[0]
    assert (row.target_status, row.target_verdict, row.ambiguity) == ("active", None, None)


def test_absent_phase_defaults_to_active(tmp_path: Path) -> None:
    _hyp(tmp_path, "0002-b", status="proposed", phase=None)
    assert inventory(tmp_path).rows[0].target_status == "active"


def test_candidate_keeps_its_verdict(tmp_path: Path) -> None:
    # Orthogonal axes: a candidate frame CAN carry a verdict.
    _hyp(tmp_path, "0003-c", status="weakened", phase="candidate")
    row = inventory(tmp_path).rows[0]
    assert (row.target_status, row.target_verdict) == ("draft", "weakened")


def test_terminal_status_is_refused_not_guessed(tmp_path: Path) -> None:
    _hyp(tmp_path, "0009-d", status="retired", phase="candidate")
    inv = inventory(tmp_path)
    assert inv.deterministic == [] and len(inv.ambiguous) == 1
    assert inv.ambiguous[0].target_status is None  # never guessed


def test_an_ADJUDICATION_lets_a_refused_file_through(tmp_path: Path) -> None:
    # THE escape from the refusal loop. Without this, `_classify` sees the terminal status
    # forever and 0009 can never migrate, no matter what an author does to the file.
    _hyp(tmp_path, "0009-d", status="retired", phase="candidate")
    adj = {
        "hypothesis:0009-d": Adjudicated(
            status="retired", verdict="weakened", closure_basis="confirmatory null, z=-0.889"
        )
    }
    inv = inventory(tmp_path, adjudication=adj)
    assert inv.ambiguous == []
    row = inv.deterministic[0]
    assert (row.target_status, row.target_verdict) == ("retired", "weakened")
    assert row.target_closure_basis == "confirmatory null, z=-0.889"


def test_adjudication_for_an_unknown_id_is_an_error(tmp_path: Path) -> None:
    # Fail early: a typo'd id in the adjudication file must not silently do nothing.
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    with pytest.raises(KeyError):
        inventory(tmp_path, adjudication={"hypothesis:9999-nope": Adjudicated(status="retired")})
```

- [ ] **Step 2: Run and fail** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/status_inventory.py
"""Plan the hypothesis lifecycle/verdict migration. Writes nothing.

The mapping is design §10 rev 7, and it INVERTS what every earlier revision assumed.
`phase` is the lifecycle; `status` was only ever the verdict. `proposed` and
`under-investigation` are not states -- they are the collapsed field's way of saying "the
evidence has not spoken", which is exactly what an ABSENT verdict already says (D1).
Mapping them to `draft` would have mis-migrated 88 of 147 files.

AMBIGUITY IS ESCAPED BY AN ARTIFACT, NEVER BY SHAPE. A file whose `status` is terminal has
lost its lifecycle, its verdict AND its closure reason at once, and no rule recovers them.
An author supplies all three in an adjudication file, keyed by entity id. Re-reading the
FILE would not help: the author's edit is indistinguishable from the corruption, so the
classifier would refuse it forever -- which is precisely the loop rev 1 shipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml
from science_model.frontmatter import split_frontmatter

from science_tool.entity_scan import iter_entity_markdown

_VERDICTS = frozenset({"supported", "weakened", "partially-supported", "refuted"})
_NO_VERDICT = frozenset({"proposed", "under-investigation"})
# An absent `phase` defaults to `active`: the template ships `phase: "active"`,
# hypotheses_cli.py:28 defaults to it, and commands/big-picture.md:62 says so.
_PHASE_TO_STATUS: dict[str | None, str] = {"candidate": "draft", "active": "active", None: "active"}
_LIFECYCLE_WORDS = frozenset({"active", "draft"})


@dataclass(frozen=True, slots=True)
class Adjudicated:
    """An author's explicit decision for a file no rule can migrate."""

    status: str
    verdict: str | None = None
    closure_basis: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryRow:
    path: Path
    entity_id: str
    status: str | None
    phase: str | None
    target_status: str | None
    target_verdict: str | None
    target_closure_basis: str | None
    ambiguity: str | None


@dataclass(frozen=True, slots=True)
class StatusInventory:
    rows: list[InventoryRow]

    @property
    def deterministic(self) -> list[InventoryRow]:
        return [r for r in self.rows if r.ambiguity is None]

    @property
    def ambiguous(self) -> list[InventoryRow]:
        return [r for r in self.rows if r.ambiguity is not None]


def load_adjudication(path: Path) -> dict[str, Adjudicated]:
    """Read an adjudication file: {entity_id: {status, verdict?, closure_basis?}}."""
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        entity_id: Adjudicated(
            status=spec["status"],
            verdict=spec.get("verdict"),
            closure_basis=spec.get("closure_basis"),
        )
        for entity_id, spec in raw.items()
    }


def _classify(
    path: Path, entity_id: str, status: str | None, phase: str | None
) -> InventoryRow:
    def row(**kw) -> InventoryRow:
        return InventoryRow(
            path=path, entity_id=entity_id, status=status, phase=phase,
            target_closure_basis=None, **kw
        )

    if status is None:
        return row(target_status=None, target_verdict=None,
                   ambiguity="no `status`: nothing to derive a verdict from")
    if phase is not None and phase not in _PHASE_TO_STATUS:
        return row(target_status=None, target_verdict=None,
                   ambiguity=f"unknown phase {phase!r} (expected candidate|active)")

    lifecycle = _PHASE_TO_STATUS[phase]

    if status in _NO_VERDICT:
        return row(target_status=lifecycle, target_verdict=None, ambiguity=None)
    if status in _VERDICTS:
        return row(target_status=lifecycle, target_verdict=status, ambiguity=None)
    if status in _LIFECYCLE_WORDS and status == lifecycle:
        # Author wrote a lifecycle word into `status`; `phase` independently agrees.
        return row(target_status=lifecycle, target_verdict=None, ambiguity=None)

    # `retired` / `archived` / anything else. A terminal word in the collapsed field
    # destroyed the lifecycle, the verdict AND the closure reason simultaneously. Nothing
    # is left to recover, and inventing any of the three would be the exact fabrication
    # this design exists to prevent.
    return row(
        target_status=None, target_verdict=None,
        ambiguity=(
            f"status {status!r} is terminal or unknown: the prior verdict and the closure "
            f"reason are unrecoverable. Adjudicate {entity_id} explicitly."
        ),
    )


def inventory(
    project_root: Path, *, adjudication: Mapping[str, Adjudicated] | None = None
) -> StatusInventory:
    adjudication = adjudication or {}
    entities_root = project_root / "entities"
    if not entities_root.is_dir():
        return StatusInventory(rows=[])

    rows: list[InventoryRow] = []
    seen: set[str] = set()
    for path in iter_entity_markdown(entities_root):
        fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        if fm.get("kind") != "hypothesis":
            continue
        entity_id = str(fm.get("id") or "")
        seen.add(entity_id)
        status = fm.get("status") or None
        phase = fm.get("phase") or None

        decided = adjudication.get(entity_id)
        if decided is not None:
            rows.append(
                InventoryRow(
                    path=path, entity_id=entity_id, status=status, phase=phase,
                    target_status=decided.status, target_verdict=decided.verdict,
                    target_closure_basis=decided.closure_basis, ambiguity=None,
                )
            )
            continue

        rows.append(
            _classify(
                path, entity_id,
                status if isinstance(status, str) else None,
                phase if isinstance(phase, str) else None,
            )
        )

    unknown = set(adjudication) - seen
    if unknown:
        raise KeyError(f"adjudication names entities that do not exist: {sorted(unknown)}")
    return StatusInventory(rows=rows)
```

- [ ] **Step 4: Green** — `6 passed`.

- [ ] **Step 5: Wire the report-only CLI** (`science entity status-inventory [--json]`), printing
  the deterministic count and each refused file with its `ambiguity`.

- [ ] **Step 6: Run against the DERIVED roster** (Task 11 Step 0 — all 18 roots, not a hand list)

```bash
uv run python -c "
import json, subprocess; from pathlib import Path
for m in json.loads(Path('/tmp/claude-1000/roster.json').read_text()):
    print('===', m['root'])
    subprocess.run(['uv','run','science','entity','status-inventory'], cwd=m['root'])"
```
Expected across all 18 roots: **145 of 147 deterministic, 2 refused** — `natural-systems/0009`, and
the missing-status toolkit fixture. The fixture **is** one of the 18 roots and **does** get migrated;
it is refused here because it authors no `status`, and it is discharged by an **explicit adjudication
entry** like any other refusal. **Fixtures get no inference shortcut** — a classifier that special-cases
test data is a classifier certified against a corpus it cannot see. **Any other refusal ⇒ the mapping
is not certified. STOP.**

- [ ] **Step 7: Commit.**

---

### Task 3b: Discharge the verdict-BASIS obligation — 0009 has an adjudication but no representable basis

> **Found by adjudicating `0009` (2026-07-12).** The two refusals are now closed by artifacts and the
> corpus is **147/147 deterministic**. But `hypothesis:0009` is adjudicated **`complete` + `refuted`**,
> and under the rev-9 contract a verdict needs a **qualifying, resolvable basis at graph time** —
> an admissible, polarity-agreeing **evidence-line** unit, or a **`falsification`** record.
>
> **`interpretation:0192` is neither.** `interpretation` is not a graph kind (design rev 9). So the
> moment Task 7's `verdict.missing-basis` ships, it would **ERROR on the flagship file of this entire
> arc** — the one whose corruption started it. *The adjudication is sound; the graph simply cannot yet
> represent what it rests on.* **A representation obligation, not adjudicative ambiguity.**

**Measured (do not re-derive):**

- `hypothesis:0009` has **zero proposition entities**. Its `P3` exists only as prose in the body
  (`entities/hypotheses/0009-…md:103` — *"P3 (empirical_regularity) — …cycle vertices carry elevated
  cross-lens disagreement"*). `natural-systems` has **no `falsification` entities at all.**
- **`FalsificationEntity.falsifies` must resolve to a `sci:Proposition`** (`entities.py:1158`,
  validated at materialization). So the falsification route **requires first promoting P3 into a
  proposition entity** — the heavier path.
- **An evidence-line CAN target a hypothesis directly.** `_evidence_targets_for_uri`
  (`graph/store/evidence_signals.py:192-195`) explicitly special-cases `sci:Hypothesis`, and the
  corpus already carries `target: hypothesis:…` lines. **This is the light path, and it is sufficient.**

- [ ] **Step 1: Author one evidence-line in `natural-systems`** — `stance: disputes`, targeting
  `hypothesis:0009-local-structure-globalization-obstruction`, sourced from
  `pipeline/t585/bridge-test-results.json` (the same source `interpretation:0192` cites).

> **⚠️ The epistemic metadata is an AUTHOR'S judgment — do not invent it.** `evidence_role`,
> `strength`, `independence`, and whether the dispute is **whole-claim/decisive** are exactly the
> knobs that decide whether `is_decisive_refutation` fires. A migration that guessed them would be
> manufacturing the evidence for the verdict it is migrating — the precise fabrication this design
> exists to prevent. **Ask; do not default.**

- [ ] **Step 2: Verify the basis resolves** — `belief_for_entity` on 0009 now sees a disputing unit,
  and `verdict.missing-basis` does **not** fire on the file.
- [x] **Step 3: Generalize the sweep — RUN 2026-07-12. The answer is "most of them."**

> ## ☠️ `verdict.missing-basis` CANNOT SHIP AS AN ERROR. It would break 11 real hypotheses on day one.
>
> Measured through the graph (`_evidence_targets_for_uri` → `collect_evidence_units`, so a
> hypothesis's evidence is counted via its linked propositions, not just lines aimed at the
> hypothesis IRI):
>
> | | n |
> |---|---|
> | hypotheses migrating to a non-null `verdict` | **15** |
> | …with evidence units in the graph | **4** *(mm30 `0001`, `0002`, `0004`, `0013`)* |
> | …**with NO representable basis** | **11** |
>
> The 11 include **`0009` itself** — the file we just adjudicated — and **5 of mm30's 6 `weakened`
> hypotheses**, in a project holding **392 evidence-lines and 334 propositions**. So this is not "the
> project lacks evidence infrastructure": those specific hypotheses have no linked propositions
> carrying evidence.
>
> **This is the original incident, about to repeat itself.** An ERROR-severity check, landing on a
> corpus never certified to satisfy it — exactly the shape that produced 472 findings and broke
> `validate` in 5 projects. *An uncertified instrument may not fail anyone's build.*
>
> **And the obvious "fix" is worse.** Refusing to migrate a verdict that has no basis would **destroy
> 11 authored adjudications**. `status: weakened` on `0026-winner-s-curse` is a real judgment its
> author made; the graph simply never recorded what it rested on. Deleting it to satisfy a check
> would be fabrication in reverse — erasing an author's conclusion because our schema cannot yet see
> its reasons. **Migrate the verdict; report the missing basis.**
>
> ### Consequences — RULED 2026-07-13
>
> 1. **`verdict.missing-basis` ships as WARN.** The basis contract stays **normative**; only its
>    *enforcement* is transitional. It carries its own **rule-specific ratchet**, separate from the
>    kind ratchet: **it remains WARN even after Task 12 adds `hypothesis` to `_CERTIFIED_KINDS`.**
>    *Kind certification and verdict-basis certification are independent facts* — the kind is
>    certified when every root is pinned and renders; the basis rule is certified when the corpus
>    actually carries bases. Neither implies the other, and collapsing them is how an uncertified
>    rule rides in on a certified one's coattails.
> 2. **`verdict.refutation-masked` is unaffected** — it fires only on `supported` + a decisive
>    refutation, and needs no basis to exist. It stays an **ERROR** and stays gated. The hard
>    invariant survives; only the coverage rule is downgraded. *(And see Task 7 Step 3c: a missing
>    basis must **not** `continue` past this check — a verdict can lack a supporting basis **and**
>    mask decisive contrary evidence at the same time. Both findings are emitted.)*
> 3. **Backfilling the deficit is real research work**, not a migration step. It is the *content* of
>    the D5 follow-through, and it is what makes `verdict` mean anything. **Track it; do not fake
>    it** — and do not block the migration on it.
>
> ### The "11" is a LOWER BOUND, not the ratchet's target
>
> This sweep counted **evidence units**, which is a *surrogate* for a basis, not the basis predicate
> itself. It establishes 11 hypotheses with **no units at all** — those cannot possibly have a basis.
> The remaining **4 are unadjudicated**: `_qualifying_basis` (Task 7) additionally demands **polarity
> agreement**, **admissibility under the belief policy**, and **core-member scope**, and any of the 4
> may fail one of those. The true deficit is therefore **≥ 11, ≤ 15**, and *only the shipped
> validator can say which*.
>
> **So the ratchet's precondition is the shipped validator's own findings — never this unit count.**
> When `verdict.missing-basis` is eventually promoted to ERROR, the gate is `science validate`
> emitting **zero** `verdict.missing-basis` findings across all 18 roots. Substituting the surrogate
> would certify against a number the instrument never produced — which is the same error, one level
> up, as grading severity on `layout_version`.

---

### Task 4: Adjudicate `natural-systems/0009` — **ADJUDICATED BY THE AUTHOR 2026-07-13**

**Not a code task.** The one real file no rule can migrate — and the file whose corruption opened
this arc (fb-2026-07-11-005).

> **This plan guessed, and it guessed wrong.** Revs 1–5 prescribed `retired` + `weakened`, reasoning
> that a non-significant confirmatory null "failed to confirm" rather than "met a rejection
> criterion." **The author ruled `complete` + `refuted`,** and the reasoning is not a matter of
> taste — it is exactly the two-axis split this whole design exists to restore:
>
> - **`complete`, not `retired`.** The pre-registered decisive test **ran** and produced an
>   unambiguous conclusion. This is *concluded research*, not pragmatically abandoned work.
>   `retired` would have asserted "stopped for non-epistemic reasons" — which is **false here**, and
>   is precisely the falsehood the collapsed `status: retired` had been telling all along.
> - **`refuted`, not `weakened`.** The hypothesis's **organizing conjecture** — not a peripheral
>   proposition — was rejected on its **sole confirmatory survival arm**, far outside the stated
>   inconclusive band and pointing the wrong way (interpretation `0192`: primary z = −0.889,
>   p = 0.819, *"null, wrong direction"*; the stratified confound control and the exploratory
>   substrate lenses are null too). `weakened` would **understate** it. P1's descriptive pattern
>   survives, but the record is explicit that any narrower claim must become a **separate
>   successor** rather than rescue 0009 as written.
>
> **The lesson for the plan, not just the file:** the implementer's inference was defensible from the
> statistics *alone* and still wrong, because the adjudication turns on what the test was **for** —
> which lives in the pre-registration and the author's judgment, not in the p-value. **This is why
> the instrument REFUSES instead of guessing.** Had `status_inventory` shipped a "reasonable
> default" here, it would have written this plan's error into the corpus and called it a migration.

- [x] **Step 1:** Read the hypothesis and its interpretations. → Done; the author adjudicated (above).
- [x] **Step 2:** **The author** (not the implementer, not this plan) supplies
  `~/d/natural-systems/.science/hypothesis-lifecycle.adjudication.yaml`:

```yaml
# Explicit authored decisions for hypotheses whose collapsed `status` destroyed the
# information needed to migrate them. Consumed by `science entity migrate-hypothesis`.
"hypothesis:0009-local-structure-globalization-obstruction":
  status: complete           # lifecycle: the decisive test RAN and concluded
  verdict: refuted           # epistemic: the organizing conjecture was rejected on its sole
                             # confirmatory arm (interpretation:0192)
```

**No `closure_basis`.** That field records why a hypothesis was closed **without** a verdict. Here
the evidence spoke, and **the verdict *is* the reason** — a `closure_basis` would be a second,
weaker copy of the adjudication.

- [x] **Step 3:** Re-run `science entity status-inventory` in natural-systems → **0 refused**.
- [x] **Step 4:** Commit the adjudication file **in natural-systems**, not in the toolkit. Commit
  *only* that file — the repo has an unrelated unstaged fetch log. → `bb4b61142`, artifact only.

> **Step 5 is a representation obligation, and it is Task 3b's, not Task 4's.** `interpretation:0192`
> is **not graph-representable as a verdict basis** under the rev-9 contract (`interpretation` is not
> an entity kind). So this file will migrate to `verdict: refuted` and *then* be reported by
> `verdict.missing-basis` — correctly, and at **WARN**. The adjudication is settled; the *basis* is
> owed. **Do not fabricate the basis to silence the warning, and do not block the migration on it.**

---

## Phase 2 — The schema substrate

### Task 5: `science-entity-base-2.0` — syntactic kind, so it never needs editing again

**Why a new base:** composition is a pure `allOf` (`validator.py:82-87`), and **an `allOf` can
only narrow.** Base 1.0 pins `kind` to `{"enum": [dataset,paper,topic,theme]}` and `id` to
`^(dataset|paper|topic|theme):…`. No extension can widen either. A base bump is forced.

**Why a *pattern*, not an enum:** there are **50 core kinds**. Rev 1 hand-typed a 26-kind enum
into base 2.0 — both incomplete *and* unevolvable, since adding kind 27 would mean **editing a
versioned schema in place**, which is the one thing versioning exists to forbid. Instead the base
constrains `kind` **syntactically** and **each mixin supplies the exact `const`**. Adding a kind
is then adding a mixin, and base 2.0 is never touched.

**Why it is safe:** every existing mixin already pins its kind — `mixin-dataset-1.0.json` has
`"kind": {"const": "dataset"}`, likewise paper/topic/theme. And `validate_as` **rejects a
base-only profile**, so a mixin is always present. The base's job is shape; the mixin's job is
identity.

**Why commons does not move:** commons records keep pinning `science-entity-base/1.0`. Two base
versions coexist — that is what versioning is *for*. **Zero commons churn.**

**Files:**
- Create: `science/model/src/science_model/schemas/science-entity-base-2.0.json`
- Test: `science/model/tests/test_base_2_0.py`

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_base_2_0.py
import json
from importlib.resources import files

import pytest

from science_model.entity_schema import EntityValidationError, EntityValidator, parse_profile


def _load(name: str) -> dict:
    return json.loads((files("science_model.schemas") / name).read_text(encoding="utf-8"))


def test_base_2_0_constrains_kind_syntactically_not_by_enum() -> None:
    # An enum would have to be edited in place every time a kind is added -- mutating a
    # versioned schema. The mixin's `const` is what pins identity.
    kind = _load("science-entity-base-2.0.json")["properties"]["kind"]
    assert "enum" not in kind
    assert kind["pattern"] == "^[a-z][a-z0-9-]*$"


def test_base_2_0_does_not_require_version_or_schema_profile() -> None:
    # `version` is a commons concept (semver on a shared record). A project entity is
    # versioned by its repo's git history. `schema_profile` is DERIVED for project kinds.
    req = _load("science-entity-base-2.0.json")["required"]
    assert "version" not in req and "schema_profile" not in req
    assert sorted(req) == ["created", "id", "kind", "title", "updated"]


def test_base_1_0_is_byte_untouched() -> None:
    # Commons pins 1.0. If this fails, 369 live commons records are at risk.
    base1 = _load("science-entity-base-1.0.json")
    assert base1["properties"]["kind"]["enum"] == ["dataset", "paper", "topic", "theme"]
    assert "version" in base1["required"]
```

> **The mixin-`const` safety argument is tested in Task 6, not here.** Executing it needs
> `validate_as`, which Task 6 introduces — so committing it in Task 5 would leave the **full suite
> red** at Task 5's commit while Step 4 ran only a green subset and declared victory. A task that
> ships a failing test has not "phased" anything; it has **broken the build and hidden it behind a
> narrow test selection.** A task ends green on `pytest`, not on `pytest -k`.

- [ ] **Step 2: Run and fail** — `SchemaNotFoundError`: the file does not exist.

- [ ] **Step 3: Create the schema.** Copy `science-entity-base-1.0.json`, keep `$defs`,
  `licenses`, `contributors`, `dataset_usage` and **every `science:merge` annotation** byte-identical,
  and change exactly these:

```json
{
  "$id": "https://schemas.science/science-entity-base-2.0.json",
  "title": "science entity base profile (kind-agnostic; mixins pin identity)",
  "required": ["id", "kind", "title", "created", "updated"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9-]*:[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
    },
    "kind": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9-]*$",
      "$comment": "Shape only. The mixin's `const` pins the exact kind — so adding a new kind never edits this versioned file."
    },
    "version": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$",
      "science:merge": "forbidden"
    }
  }
}
```

Deltas, and only these: **(a)** `$id`/`title`; **(b)** `required` drops `schema_profile` (derived
for project kinds) and `version` (a commons concept); **(c)** `kind` becomes a pattern; **(d)**
`id` becomes prefix-agnostic, with the suffix widened to 127 chars — hypothesis slugs like
`0009-local-structure-globalization-obstruction` exceed base 1.0's 64.

- [ ] **Step 4: Green — the WHOLE suite**, not a selection. `cd science/model && uv run --frozen
  pytest`, then `cd science && uv run --frozen pytest`. Task 5 adds a schema file and three
  file-shape tests; nothing it commits can be red.

- [ ] **Step 5: Commit.**

---

### Task 6: Profile plumbing, `validate_as`, and `mixin-hypothesis-1.0`

**One task, because the mixin's invariants and the machinery that executes them cannot go green
separately** — and **no task may end red.**

**Files:**
- Modify: `science/model/src/science_model/entity_schema/profile.py`, `validator.py`
- Create: `science/model/src/science_model/schemas/mixin-hypothesis-1.0.json`
- Test: `science/model/tests/test_project_profiles.py`, `test_mixin_hypothesis.py`

**Interfaces:**
- Produces `EntityValidator.validate_as(entity: dict, profile: ProfileString) -> None` — validate
  against an **explicit** profile. Project entities do **not** carry `schema_profile` in
  frontmatter; it is derived from `kind`. Tasks 8–10 call this.
- Produces `default_profile_for_kind("hypothesis")` → `science-entity-base/2.0+hypothesis/1.0`.

- [ ] **Step 1: Write the failing tests**

```python
# science/model/tests/test_project_profiles.py
import pytest

from science_model.entity_schema import default_profile_for_kind, parse_profile
from science_model.entity_schema.profile import ProfileParseError


def test_hypothesis_derives_a_base_2_profile() -> None:
    assert default_profile_for_kind("hypothesis").render() == "science-entity-base/2.0+hypothesis/1.0"


def test_commons_kinds_stay_on_base_1() -> None:
    # Non-negotiable: 369 live commons records pin base 1.0.
    assert default_profile_for_kind("dataset").render() == "science-entity-base/1.0+dataset/1.0"
    assert default_profile_for_kind("paper").render() == "science-entity-base/1.0+paper/2.0"


def test_unknown_mixin_still_rejected() -> None:
    with pytest.raises(ProfileParseError):
        parse_profile("science-entity-base/2.0+nonsense/1.0")


def test_a_mixin_const_still_narrows_the_kind_under_base_2() -> None:
    # MOVED HERE FROM TASK 5: it needs `validate_as`, which lands in this task.
    #
    # Base 2.0's `kind` is a PATTERN, so the base alone would accept any lowercase word. The
    # entire safety argument for widening it is that the mixin re-pins the kind with a `const`.
    # Untested, that argument is a comment. Here it is, executed: a `hypothesis` payload cannot
    # ride in on the dataset mixin.
    with pytest.raises(EntityValidationError):
        EntityValidator().validate_as(
            {"id": "dataset:x", "kind": "hypothesis", "title": "T",
             "created": "2026-07-12", "updated": "2026-07-12",
             "origin": "external", "tier": "raw"},
            parse_profile("science-entity-base/2.0+dataset/1.0"),
        )
```

```python
# science/model/tests/test_mixin_hypothesis.py
import json
from importlib.resources import files

import pytest

from science_model.entity_schema import (
    EntityValidationError, EntityValidator, default_profile_for_kind,
)
from science_model.profiles.core import CORE_PROFILE

PROFILE = default_profile_for_kind("hypothesis")
V = EntityValidator()


def _h(**over) -> dict:
    base = {"id": "hypothesis:0001-x", "kind": "hypothesis", "title": "T",
            "created": "2026-07-12", "updated": "2026-07-12", "status": "active"}
    base.update(over)
    return base


def test_lifecycle_vocabulary_is_the_ruled_one() -> None:
    for good in ("draft", "active"):
        V.validate_as(_h(status=good), PROFILE)
    for verdict_word in ("proposed", "under-investigation", "supported", "weakened"):
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(status=verdict_word), PROFILE)


def test_verdict_excludes_the_unassessed_spellings() -> None:
    V.validate_as(_h(verdict="refuted"), PROFILE)
    for bad in ("proposed", "under-investigation"):
        # D1: absence already means "not yet assessed". Admitting these makes three
        # spellings of one state and re-collapses the axis.
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(verdict=bad), PROFILE)


def test_the_axes_are_orthogonal() -> None:
    # The cell the collapsed field could not express.
    V.validate_as(_h(status="superseded", verdict="supported",
                     superseded_by="hypothesis:0002-y"), PROFILE)
    V.validate_as(_h(status="draft", verdict="weakened"), PROFILE)


def test_complete_REQUIRES_a_verdict() -> None:
    # RULED (design rev 6): prohibited outright, NOT dischargeable by closure_basis.
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="complete"), PROFILE)
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="complete", closure_basis="ran out of time"), PROFILE)
    V.validate_as(_h(status="complete", verdict="supported"), PROFILE)


def test_retired_always_requires_a_closure_basis() -> None:
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="retired"), PROFILE)
    V.validate_as(_h(status="retired", closure_basis="no samples left"), PROFILE)


def test_superseded_requires_lineage_or_a_basis() -> None:
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="superseded"), PROFILE)
    V.validate_as(_h(status="superseded", superseded_by="hypothesis:0002-y"), PROFILE)
    # `resynthesized_into` is a LIST (archive.py:38, materialize.py:155) -- not a string.
    V.validate_as(_h(status="superseded", resynthesized_into=["hypothesis:0002-y"]), PROFILE)
    V.validate_as(_h(status="superseded", closure_basis="folded into h5"), PROFILE)


def test_phase_and_disposition_are_FORBIDDEN() -> None:
    for gone in ({"phase": "candidate"}, {"disposition": "closed"},
                 {"disposition_basis": "x"}):
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(**gone), PROFILE)


def test_an_arbitrary_unknown_key_is_REJECTED() -> None:
    # Rev 1's test used `phase`, which is explicitly `false` in the schema -- so it proved
    # nothing about unknown keys. THE original defect is that `Entity` is extra="ignore"
    # and silently DROPS anything undeclared. This is the test that actually pins it.
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(role_typo="oops"), PROFILE)


@pytest.mark.parametrize("derived", ["schema_profile", "version"])
def test_DERIVED_fields_cannot_be_AUTHORED_on_a_project_kind(derived: str) -> None:
    # "`schema_profile` is derived; `version` is a commons concept" is only DOCUMENTATION until
    # something rejects the authored spelling. Base 2.0 keeps both as optional generic properties
    # (commons records on base 1.0 still author them), so the base cannot be where this is said --
    # `mixin-hypothesis` must set BOTH to `false`.
    #
    # Otherwise the failure is silent and self-inflicted: an author writes
    # `schema_profile: science-entity-base/1.0+hypothesis/1.0`, the schema accepts it, and the
    # entity is now validated against a profile it chose for itself. A derived field an author can
    # set is not derived -- it is a second, unversioned source of truth. That is the exact shape of
    # the `status`/`phase` collapse this whole arc exists to undo.
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(**{derived: "1.0.0"}), PROFILE)


def test_the_mixin_says_so_STRUCTURALLY_not_just_behaviorally() -> None:
    # Pin the mechanism, so a later refactor cannot make the two tests above pass by accident
    # (e.g. via `unevaluatedProperties: false` alone) and then regress when the base changes.
    mixin = json.loads(
        (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
    )
    assert mixin["properties"]["schema_profile"] is False
    assert mixin["properties"]["version"] is False


def test_every_authored_field_in_the_corpus_is_DECLARED() -> None:
    # The P0 gate, executed. Task 2 adjudicated 36 keys; if the mixin declares fewer, then
    # closing the schema rejects real files. This is the test that would have caught rev 1.
    schema = json.loads(
        (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
    )
    base = json.loads(
        (files("science_model.schemas") / "science-entity-base-2.0.json").read_text(encoding="utf-8")
    )
    declared = set(schema["properties"]) | set(base["properties"])
    adjudicated = set(ADJUDICATED_HYPOTHESIS_FIELDS)  # from Task 2's doc; pin it here
    assert adjudicated - {"phase"} <= declared


def test_schema_and_descriptor_agree() -> None:
    # The bidirectional gate. A vocabulary that disagrees with its descriptor is exactly the
    # uncertified instrument that broke five projects.
    schema = json.loads(
        (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
    )
    descriptor = next(k for k in CORE_PROFILE.entity_kinds if k.name == "hypothesis")
    assert sorted(schema["properties"]["status"]["enum"]) == sorted(descriptor.statuses)
```

> `test_schema_and_descriptor_agree` needs the Task 8 descriptor. **Do not xfail it** (rev 1 did,
> and an xfail is a red suite wearing a hat). Move the descriptor change **into Task 8** and this
> test **into Task 8's file** — it belongs with the change it gates.

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Implement the profile plumbing.** In `profile.py` replace line 16 and lines 75–102:

```python
BASE_NAME = "science-entity-base"

# Commons type mixins (base 1.0). Shared across repos; versioned; 369 live records.
COMMONS_MIXIN_NAMES = frozenset({"dataset", "paper", "topic", "theme"})

# Project-authored kinds converging onto the same schema system (base 2.0). This set IS the
# P2m slice list: one entry per migrated kind.
PROJECT_MIXIN_NAMES = frozenset({"hypothesis"})

TYPE_MIXIN_NAMES = COMMONS_MIXIN_NAMES | PROJECT_MIXIN_NAMES
```

```python
_DEFAULT_MIXIN_VERSION: dict[str, str] = {
    "dataset": "1.0", "paper": "2.0", "topic": "2.0", "theme": "2.0",
    "hypothesis": "1.0",
}

# The base version is PER-KIND, not global. Commons kinds pin base 1.0 -- 369 live records
# depend on it and there is no reason to move them. Project kinds need base 2.0, whose
# kind/id constraints admit them (base 1.0's structurally cannot, and an allOf can only
# narrow). Two base versions coexisting is what versioning is FOR.
_BASE_VERSION_FOR_MIXIN: dict[str, str] = {
    **{name: "1.0" for name in COMMONS_MIXIN_NAMES},
    **{name: "2.0" for name in PROJECT_MIXIN_NAMES},
}


def default_profile_for_kind(kind: str) -> ProfileString:
    """The default profile for a kind.

    Project entities do NOT carry `schema_profile` in frontmatter -- it is derived here.
    (Commons records DO carry it: they travel between repos, so the profile must travel with
    the record. A project entity is versioned by the repo that contains it.)
    """
    if kind not in _DEFAULT_MIXIN_VERSION:
        raise ProfileParseError(
            f"unknown kind {kind!r}; expected one of {sorted(_DEFAULT_MIXIN_VERSION)}"
        )
    return parse_profile(
        f"{BASE_NAME}/{_BASE_VERSION_FOR_MIXIN[kind]}+{kind}/{_DEFAULT_MIXIN_VERSION[kind]}"
    )
```

In `validator.py`, add `validate_as`, make `validate` delegate, and **close the composed schema**:

```python
    def validate(self, entity: dict[str, Any]) -> None:
        """Validate against the entity's OWN declared `schema_profile` (the commons path)."""
        profile_str = entity.get("schema_profile")
        if not profile_str:
            raise EntityValidationError("entity is missing required schema_profile field")
        try:
            profile = parse_profile(profile_str)
        except ProfileParseError as exc:
            raise EntityValidationError(f"invalid schema_profile: {exc}") from exc
        self.validate_as(entity, profile)

    def validate_as(self, entity: dict[str, Any], profile: ProfileString) -> None:
        """Validate against an EXPLICIT profile, without mutating the caller's dict."""
        if profile.mixin is None:
            raise EntityValidationError(
                f"schema_profile must include a type mixin (one of {sorted(TYPE_MIXIN_NAMES)}) "
                f"— base-only profiles are not valid for entity payloads"
            )
        composed = self._compose(profile)
        validator = Draft202012Validator(
            composed, format_checker=Draft202012Validator.FORMAT_CHECKER
        )
        errors = sorted(validator.iter_errors(entity), key=lambda e: list(e.absolute_path))
        if errors:
            joined = "; ".join(_format_error(err) for err in errors)
            raise EntityValidationError(f"entity failed schema validation: {joined}", errors=errors)

    def _compose(self, profile: ProfileString) -> dict[str, Any]:
        parts = [self._loader.load(profile.base)]
        if profile.mixin is not None:
            parts.append(self._loader.load(profile.mixin))
        parts.extend(self._loader.load(ext) for ext in profile.extensions)

        # `unevaluatedProperties` -- NOT `additionalProperties`. Inside an allOf,
        # `additionalProperties` in one branch cannot see properties declared by a SIBLING
        # branch, so it would reject every field the mixin declares. `unevaluatedProperties`
        # is evaluated after the whole allOf and sees the union. This is THE line that turns
        # the original defect (extra="ignore" silently dropping undeclared keys) into a loud
        # failure -- and it is why Task 2's field adjudication is a hard prerequisite: an
        # undeclared-but-authored key becomes a validation error the moment this lands.
        strict = profile.mixin.name in PROJECT_MIXIN_NAMES
        composed: dict[str, Any] = {"allOf": parts}
        if strict:
            composed["unevaluatedProperties"] = False
        return composed
```

> **Commons profiles are deliberately NOT closed.** `SharedEntity` is `extra="allow"` by design
> and 369 records rely on it; closing commons is a separate decision with a separate blast radius.
> `strict` is gated on `PROJECT_MIXIN_NAMES` so each kind opts in **as it migrates**.

- [ ] **Step 3b: Write `mixin-hypothesis-1.0.json`.** `properties` contains **exactly the keys Task 2
  adjudicated as `core`** — the 25 core fields plus the 3 deferred-capability fields. It does
  **NOT** contain the project-extension fields (`confidence_label`, `confidence_mechanistic_label`,
  `evidence_scope`); those compose in from the project's own extension (Task 6b). It does **NOT**
  contain `belief_state` (deleted — derived), `phase`, `disposition`, or `profile`.
  Abridged below to the fields this slice reasons about — **the implementer writes the full core
  list from Task 2's doc, and `test_every_authored_field_in_the_corpus_is_DECLARED` enforces that
  every corpus key is covered by the mixin *or* by a composed project extension:**

> **`schema_profile: false` and `version: false` are load-bearing, not decoration.** Base 2.0 keeps
> both as **optional generic properties** — commons records (base 1.0) legitimately author them, and
> the base is shared — so **the base cannot forbid them and the MIXIN must.** Without those two
> lines, `default_profile_for_kind` is merely a *suggestion*: an author writes
> `schema_profile: science-entity-base/1.0+hypothesis/1.0` in frontmatter and **the entity chooses
> the schema it is judged by.** *A derived field an author can set is not derived — it is a second,
> unversioned source of truth,* which is the exact collapse (`status` vs `phase`) this arc exists to
> undo. Note `unevaluatedProperties: false` alone would **not** catch this: the base *declares* both
> keys, so they are evaluated and permitted. The mixin's `false` is the only thing that says no.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/mixin-hypothesis-1.0.json",
  "title": "hypothesis type mixin",
  "type": "object",
  "required": ["id", "kind", "status"],
  "properties": {
    "kind": { "const": "hypothesis" },

    "status": {
      "description": "LIFECYCLE. Not the verdict. Sourced from the old `phase` field (design rev 7).",
      "enum": ["draft", "active", "complete", "superseded", "retired", "archived"]
    },
    "verdict": {
      "description": "EPISTEMIC. What the evidence concludes. ABSENT = not yet assessed -- which is why `proposed`/`under-investigation` are NOT admitted: they would be a third spelling of absence.",
      "enum": ["partially-supported", "supported", "weakened", "refuted"]
    },
    "closure_basis": {
      "description": "The AUTHORED reason a terminal entity closed, required when no structural basis exists. The state is derivable; the reason is not.",
      "type": "string", "minLength": 1
    },

    "superseded_by": { "type": "string", "pattern": "^hypothesis:" },
    "resynthesized_into": {
      "type": "array", "items": { "type": "string", "pattern": "^hypothesis:" },
      "$comment": "A LIST — see archive.py:38 and materialize.py:155."
    },
    "archive_ref": { "type": "string" },

    "related": { "type": "array", "items": { "type": "string" } },
    "source_refs": { "type": "array", "items": { "type": "string" } },
    "origins": { "type": "array" },
    "added_by": { "type": "string" },
    "tags": { "type": "array", "items": { "type": "string" } },
    "ontology_terms": { "type": "array", "items": { "type": "string" } },
    "datasets": { "type": "array" },
    "lens_views": { "type": "array" },
    "priority": {},
    "role": { "type": "string" },
    "domain": { "type": "string" },
    "description": { "type": "string" },
    "aliases": { "type": "array", "items": { "type": "string" } },
    "review_state": {},
    "promoted_from": { "type": "string" },
    "promotion_criteria": {},
    "rival_model_packet": {},
    "external_hypothesis_id": { "type": "string" },
    "identification": {},

    "required_capabilities": { "type": "array", "$comment": "P1 subsystem — declared, not yet absorbed." },
    "capability_scope": {},
    "composition_rule": {},

    "phase": false,
    "disposition": false,
    "disposition_basis": false,
    "profile": false,

    "schema_profile": false,
    "version": false
  },

  "allOf": [
    {
      "$comment": "RULED (rev 6): you cannot conclude without concluding something. `closure_basis` does NOT discharge this — admitting `complete` + absent-verdict would give `retired + closure_basis` a second spelling that reads, to every consumer, as though the hypothesis had been resolved.",
      "if": { "properties": { "status": { "const": "complete" } }, "required": ["status"] },
      "then": { "required": ["verdict"] }
    },
    {
      "$comment": "`retired` is the only terminal with no structural basis available to it, so it ALWAYS requires an authored one. This is the fb-005 no-hidden-debt guarantee.",
      "if": { "properties": { "status": { "const": "retired" } }, "required": ["status"] },
      "then": { "required": ["closure_basis"] }
    },
    {
      "$comment": "PRESENCE only. Whether the lineage RESOLVES is a cross-record fact and belongs to resolution.py — the schema cannot see other files. Keying off the status word alone would be unsound: the live-lineage contract explicitly permits a live `superseded` with no lineage.",
      "if": { "properties": { "status": { "const": "superseded" } }, "required": ["status"] },
      "then": { "anyOf": [ { "required": ["superseded_by"] }, { "required": ["resynthesized_into"] }, { "required": ["closure_basis"] } ] }
    },
    {
      "if": { "properties": { "status": { "const": "archived" } }, "required": ["status"] },
      "then": { "anyOf": [ { "required": ["archive_ref"] }, { "required": ["closure_basis"] } ] }
    }
  ]
}
```

> `"phase": false` is the JSON Schema idiom for *"this property must not appear."* It makes the
> deletion **enforced**, not merely intended. `"profile": false` keeps a derived field from being
> hand-authored (3 files do today — Task 8 strips it).

- [ ] **Step 4: Green** — the whole model suite, including Task 5's fourth test.

```bash
cd science/model && uv run --frozen pytest -q
```

- [ ] **Step 5: Commit.**

---

### Task 6b: Project extensions — compose them BEFORE closing the schema

**Without this, `unevaluatedProperties: false` rejects mm30's `confidence_mechanistic_label` — so
the only way to keep mm30 validating would be to promote a one-project field into the core mixin
for all 22 projects.** That is design §6's ownership contract, violated. **Strictness and
project-local fields must arrive together, or strictness cannot arrive at all.**

Design §6 already names the mechanism: an **additive-only extension component** in the profile,
which may *add* fields to a core kind but never redefine a core one.

**Files:**
- Modify: `science/model/src/science_model/entity_schema/loader.py` — search a project schema dir before package resources
- Modify: `science/model/src/science_model/entity_schema/profile.py` — `resolve_profile(kind, extensions)`
- Modify: `science/src/science_tool/` — read `entity_extensions` from `science.yaml`
- Create: `~/d/cancer/cancer-types/multiple-myeloma/schemas/extension-mm30.assessment-1.0.json` *(in mm30, not the toolkit)*
- Test: `science/model/tests/test_project_extensions.py`

**Interfaces:**
- Produces `resolve_profile(kind: str, *, extensions: list[str]) -> ProfileString` — the default
  base+mixin plus the project's declared extensions. **Tasks 7, 9 and 10 call this, not
  `default_profile_for_kind`.** (`default_profile_for_kind` remains the zero-extension case.)

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_project_extensions.py
def test_an_extension_ADDS_a_field_without_touching_the_core_mixin(tmp_schema_dir) -> None:
    _write_extension(tmp_schema_dir, "extension-mm30.assessment-1.0.json", {
        "properties": {"confidence_mechanistic_label": {"type": "string"}}
    })
    profile = resolve_profile("hypothesis", extensions=["mm30.assessment/1.0"])
    EntityValidator(SchemaLoader(project_dir=tmp_schema_dir)).validate_as(
        _h(confidence_mechanistic_label="high"), profile
    )


def test_the_SAME_field_is_rejected_WITHOUT_the_extension(tmp_schema_dir) -> None:
    # This is the whole point: the field is legal for mm30 and illegal everywhere else.
    # If this passes without the extension, the mixin swallowed a project field.
    with pytest.raises(EntityValidationError):
        EntityValidator().validate_as(
            _h(confidence_mechanistic_label="high"), default_profile_for_kind("hypothesis")
        )


def test_an_extension_may_NOT_redefine_a_core_field(tmp_schema_dir) -> None:
    # Additive ONLY (design §6). An allOf can only narrow, so a redefinition would silently
    # INTERSECT with the core enum rather than replace it -- producing an unsatisfiable schema
    # rather than an error. Catch it at load, loudly.
    _write_extension(tmp_schema_dir, "extension-bad.x-1.0.json", {
        "properties": {"status": {"enum": ["whatever"]}}
    })
    with pytest.raises(ExtensionRedefinesCoreField, match="status"):
        resolve_profile("hypothesis", extensions=["bad.x/1.0"],
                        loader=SchemaLoader(project_dir=tmp_schema_dir))
```

> The third test is the one that matters. Because composition is a pure `allOf`, an extension
> redefining `status` does **not** override the core enum — it **intersects** with it, yielding a
> schema nothing can satisfy. The failure would surface as *"this valid file is invalid"* with no
> hint why. **Reject redefinition at load time**, by name.

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Implement.** `SchemaLoader(project_dir: Path | None)` checks `project_dir` first,
  then falls back to `importlib.resources` (package schemas). `resolve_profile` appends the parsed
  extension components and raises `ExtensionRedefinesCoreField` if any extension's `properties`
  intersect the base's or mixin's. `science.yaml` gains:

```yaml
entity_schema_version: 2
entity_extensions:
  hypothesis: ["mm30.assessment/1.0"]   # resolves to schemas/extension-mm30-assessment-1.0.json
```

- [ ] **Step 4: Green** — model suite + a real mm30 dry run (`science validate` in `~/d/cancer/cancer-types/multiple-myeloma`
  with the extension declared: **exit 0**; with it removed: the 12 files **fail loudly**, which is
  the proof the field is genuinely project-scoped and not silently core).

- [ ] **Step 5: Commit** (toolkit and mm30 separately — different repos).

---

### Task 7: `resolution.py` — the cross-record layer, **wired**

Schema validates **one record in isolation**. It cannot resolve a successor ID or confirm an
archive record exists. **Presence is schema; resolution is a validator.** Without this, a
*present but dangling* `superseded_by:` satisfies the schema and closes the entity with no real
reason behind it — the hole in a subtler dress.

> **Scope, stated honestly — and one of the two moved.** Design §7.4 lists three cross-record
> invariants. This module ships **two at load time**: successor resolution and archive-record
> existence. The third — **every authored verdict has qualifying, resolvable evidence** — is a
> **graph-time** fact (it needs evidence-line edges, which exist only after materialization), so
> it ships as a **graph check** (Step 3c below), not here. Rev 1 claimed all three and
> implemented one; rev 2 deferred the third; **rev 3 implements it, in the right layer.**
>
> **And its trigger is corrected (design rev 8).** Rev 2 scoped it to `status: complete`. **Wrong
> — it applies to EVERY authored verdict.** A `draft` hypothesis asserting `verdict: refuted` with
> no evidence behind it is a fabrication whatever its lifecycle says; gating on `complete` would
> have left the front door open. **`verdict` is an evidence-constrained adjudication** (rev 8's
> contract), and the constraint is not conditional on the lifecycle.

**Files:**
- Create: `science/model/src/science_model/entity_schema/resolution.py`
- Modify: `science/src/science_tool/graph/sources.py`, `entities.py` (`edit_entity`), `validate/checks/`
- Test: `science/model/tests/test_resolution.py`, `science/tests/test_resolution_wiring.py`

- [ ] **Step 1: Write the failing tests** — unit **and wiring**. Rev 1 shipped the module unwired
  and admitted it in its own self-review. **The wiring tests are the point.**

```python
# science/model/tests/test_resolution.py
from science_model.entity_schema.resolution import check_resolution

KNOWN = {"hypothesis:0002-y"}


def test_dangling_successor_is_caught() -> None:
    # The whole reason this module exists: the schema is satisfied, the entity is closed,
    # and the reason it closed does not exist.
    v = check_resolution(
        {"id": "hypothesis:0001-x", "status": "superseded",
         "superseded_by": "hypothesis:9999-nope"},
        known_ids=KNOWN, known_archive_refs=set(),
    )
    assert len(v) == 1 and "9999-nope" in v[0]


def test_resolving_successor_passes() -> None:
    assert check_resolution(
        {"id": "hypothesis:0001-x", "status": "superseded",
         "superseded_by": "hypothesis:0002-y"},
        known_ids=KNOWN, known_archive_refs=set(),
    ) == []


def test_resynthesized_into_is_a_LIST_and_every_member_must_resolve() -> None:
    v = check_resolution(
        {"id": "hypothesis:0001-x", "status": "superseded",
         "resynthesized_into": ["hypothesis:0002-y", "hypothesis:9999-nope"]},
        known_ids=KNOWN, known_archive_refs=set(),
    )
    assert len(v) == 1 and "9999-nope" in v[0]


def test_self_supersession_is_caught() -> None:
    v = check_resolution(
        {"id": "hypothesis:0002-y", "status": "superseded",
         "superseded_by": "hypothesis:0002-y"},
        known_ids=KNOWN, known_archive_refs=set(),
    )
    assert len(v) == 1 and "itself" in v[0]


def test_dangling_archive_ref_is_caught() -> None:
    v = check_resolution(
        {"id": "hypothesis:0001-x", "status": "archived", "archive_ref": "arc:nope"},
        known_ids=KNOWN, known_archive_refs={"arc:real"},
    )
    assert len(v) == 1 and "arc:nope" in v[0]


def test_a_basis_closed_entity_needs_no_structure() -> None:
    assert check_resolution(
        {"id": "hypothesis:0001-x", "status": "superseded", "closure_basis": "folded into h5"},
        known_ids=KNOWN, known_archive_refs=set(),
    ) == []


def test_a_live_entity_is_not_checked() -> None:
    assert check_resolution(
        {"id": "hypothesis:0001-x", "status": "active"},
        known_ids=set(), known_archive_refs=set(),
    ) == []
```

```python
# science/tests/test_resolution_wiring.py
def test_validate_reports_a_dangling_successor(tmp_project) -> None:
    write_hypothesis(tmp_project, "0001-x", status="superseded",
                     extra={"superseded_by": "hypothesis:9999-nope"})
    findings = run_validate(tmp_project)
    assert any("9999-nope" in f.message for f in findings)


def test_edit_entity_refuses_a_dangling_successor(tmp_project) -> None:
    write_hypothesis(tmp_project, "0001-x", status="active")
    with pytest.raises(EntityCommandError, match="9999-nope"):
        edit_entity(tmp_project, "hypothesis:0001-x",
                    status="superseded", superseded_by="hypothesis:9999-nope")
    # FAILS BEFORE WRITING.
    assert 'status: "active"' in (tmp_project / "entities/hypotheses/0001-x.md").read_text()
```

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Implement**

```python
# science/model/src/science_model/entity_schema/resolution.py
"""Cross-record invariants — the D3 escape hatch, ENUMERATED.

JSON Schema is the authority for a record's SHAPE and for the PRESENCE of a structural basis.
It validates one record in isolation, so it structurally cannot answer: does this successor ID
resolve? does that archive record exist? Those are cross-record facts.

This is that second layer, and it is deliberately a CLOSED LIST rather than an open-ended
second authority (design §9, D3). Getting the split wrong re-opens the hole it was built to
close: a PRESENT but DANGLING `superseded_by:` satisfies the schema, closes the entity, and
records no real reason for the closure.

NOT HERE: "a verdict has qualifying evidence". That needs the evidence-line EDGES, which exist
only after materialization -- it is a graph-time invariant, and this runs at load time. Design
§7.4 names it; it belongs to a graph check, not to this module. Said plainly so nobody assumes
it is covered.
"""

from __future__ import annotations

from typing import Any

_TERMINALS_WITH_STRUCTURE = frozenset({"superseded", "archived"})


def _lineage_refs(entity: dict[str, Any]) -> list[tuple[str, str]]:
    """(field, ref) pairs. `superseded_by` is scalar; `resynthesized_into` is a LIST."""
    refs: list[tuple[str, str]] = []
    scalar = entity.get("superseded_by")
    if isinstance(scalar, str) and scalar:
        refs.append(("superseded_by", scalar))
    listed = entity.get("resynthesized_into")
    if isinstance(listed, list):
        refs.extend(("resynthesized_into", r) for r in listed if isinstance(r, str) and r)
    return refs


def check_resolution(
    entity: dict[str, Any], *, known_ids: set[str], known_archive_refs: set[str]
) -> list[str]:
    """Violations of cross-record terminal invariants. Empty == clean."""
    if entity.get("status") not in _TERMINALS_WITH_STRUCTURE:
        return []

    entity_id = str(entity.get("id") or "<unknown>")
    violations: list[str] = []

    for field, ref in _lineage_refs(entity):
        if ref == entity_id:
            violations.append(f"{entity_id}: {field} points at itself")
        elif ref not in known_ids:
            violations.append(
                f"{entity_id}: {field} -> {ref!r} does not resolve to any known entity; "
                f"the entity is closed and the reason it closed does not exist"
            )

    archive_ref = entity.get("archive_ref")
    if isinstance(archive_ref, str) and archive_ref and archive_ref not in known_archive_refs:
        violations.append(
            f"{entity_id}: archive_ref -> {archive_ref!r} does not resolve to any archive record"
        )
    return violations
```

- [ ] **Step 3b: WIRE it — three call sites, none optional**
  1. **`graph/sources.py`**, after the whole corpus is loaded (it needs `known_ids`, so it is a
     *second pass*, not per-file): collect all entity ids and archive refs
     (`archive.py`'s index), then `check_resolution` each terminal entity; append a
     `SourceFailure`/warning per violation.
  2. **`validate/checks/`** — a new check surfacing those violations as `Result`s at **WARN**
     (ERROR arrives with Task 12's ratchet, per kind).
  3. **`entities.edit_entity`** — before writing, so a terminal transition with a dangling
     successor **fails before a byte is written** (Task 10).

> ### ⚠️ Task 2b orphaned three guarantees — but a VERDICT IS NOT AN ORDINAL BELIEF LADDER.
>
> Deleting `_authored_magnitude` (Task 2b, shipped) removed the only input to three shipped rules
> from the 2026-05-22 belief design. They were **provably dead on the corpus** (every real file sits
> at rung 0; every rule needs a higher rung), so the deletion was behavior-neutral. **But the
> invariants they encoded are not dead** — they guarded *an author asserting an epistemic claim the
> evidence does not support*, which is now exactly what an authored **`verdict`** is.
>
> **My first attempt re-homed them as one-to-one renames. That was wrong, and it is worth naming why.**
> `speculative → fragile → supported → well_supported` is an **ordinal magnitude**.
> `supported | partially-supported | weakened | refuted` is **not a ladder at all** — it is a set of
> *adjudications*, and ordinalizing them produces nonsense:
>
> - A decisive refutation of **one constituent proposition** is perfectly compatible with
>   `partially-supported`. On a ladder it reads as a contradiction.
> - **`weakened` is temporal.** It asserts a *change*, and **cannot be inferred from a single current
>   belief snapshot** — it needs a prior one.
> - **One decisive independent test can legitimately establish `refuted`.** So a
>   "single-source ceiling" applied to `refuted` would flag exactly the strongest possible refutation.
>   The ceiling doesn't just fail to transfer — **it inverts.**
>
> So there is no rename. There is a **compatibility matrix**, and only one hard invariant.
>
> | verdict | minimum agreement check | severity |
> |---|---|---|
> | `supported` | composed belief supports it; a **decisive whole-hypothesis / core-conjunction refutation is an ERROR** | **ERROR** on refutation |
> | `partially-supported` | some support **plus** unresolved / disputed / unsupported portions. **Never ordinalized** — a refuted member is *expected here*, not contradictory. | report |
> | `weakened` | disputing evidence or a negative adjudication basis. **Historical weakening requires a prior snapshot** — do not infer a trajectory from one. | report |
> | `refuted` | a decisive refutation **or** an explicitly linked negative adjudication. **No single-source ceiling.** | report |
>
> | rule | severity | what it is |
> |---|---|---|
> | **`verdict.refutation-masked`** | **ERROR**, re-gated in `gates.py` | **The hard invariant.** `supported` while an unresolved decisive whole-hypothesis or **core-conjunction** refutation stands. |
> | **`verdict.missing-basis`** | **WARN** (ruled 2026-07-13; see Task 3b) | An authored verdict with **no qualifying basis at all**. The contract is normative; **enforcement is transitional** — ≥11 of the 15 migrating verdicts cannot satisfy it today. It has its **own** ratchet, and stays WARN even after Task 12 certifies the *kind*. |
> | **`verdict.disagrees-with-computed`** | WARN, report-only | The authored adjudication and the composed belief disagree. **Explanatory, not a ceiling.** |
>
> The last two are **explanatory disagreement reports**, not ports of the deleted ordinal rules.
> Licensed by rev 8 point 4 — *computed systems may report a recommendation or disagreement, and must
> **never** populate or overwrite the authored verdict.* The belief axis had to be policed because
> belief was **authored**; the verdict axis is policed because adjudication **should be**.

> ### ⚠️ Use COMPOSED hypothesis belief — not a flattened evidence pool.
>
> An earlier draft called
> `aggregate_belief(collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(uri)))`.
> That **merges every member's evidence into one pool**, so strong evidence for one proposition can
> **hide a speculative core member** — the precise failure `roll_up_weakest_link` exists to prevent.
>
> **The authoritative hypothesis computation already exists: `bundle_belief.belief_for_entity()`**
> (`graph/bundle_belief.py:180`). It dispatches hypothesis → `BundleBeliefResult`, whose
> `member_results` / `bottleneck_members` / `unresolved_members` / `contested_members` are exactly the
> vocabulary the matrix above needs — and it keeps **`capped_by_refutation` as a SEPARATE boolean
> axis, never folded into the magnitude ordinal** (`bundle_belief.py:133-137`), which is the same
> distinction this whole correction rests on. Use it. Do not re-derive it.
>
> **Check direct whole-hypothesis refutations SEPARATELY.** When a hypothesis has core members,
> `belief_for_entity` takes the bundle branch (`:215+`) and **never calls
> `collect_evidence_units([uri])`** — so a decisive refutation attached *directly to the hypothesis*
> is invisible to it. **Bundle dispatch would hide the very thing `refutation-masked` must catch.**

> ### ⚠️ `check_verdict_has_evidence` overclaimed — and so does the CONTRACT.
>
> The drafted body tested `if not units`, which establishes only that **an edge exists**. It does not
> establish:
> - **polarity agreement** — a `supports` line is not a basis for `refuted`;
> - **admissibility** under the belief policy — a unit the policy excludes is not a basis;
> - **an interpretation basis** — the code never read interpretations.
>
> **And it cannot.** `interpretation` **is not an entity kind in the graph** — the registry holds
> `evidence-line`, `falsification`, `hypothesis`, `mechanism`, `proposition`, … and **no
> `interpretation`**, and no interpretation→hypothesis predicate exists. So design rev 8's contract
> clause *"qualifying, resolvable evidence **or interpretation basis**"* is **unimplementable as
> written**. That is a defect in the **contract**, not just in the draft code.
>
> **Resolution — scope it explicitly, do not quietly claim it.** A qualifying basis is:
> 1. an **admissible, polarity-agreeing evidence-line unit** on the hypothesis or a core member, and/or
> 2. a **`falsification`** record (`FalsificationEntity.falsifies` → proposition,
>    `materialize.py:1230`) on the hypothesis or a core member — this is the *"explicitly linked
>    negative adjudication"* the `refuted` row calls for.
>
> **Interpretations are OUT OF SCOPE until they reach the graph.** Either wire them (a separate
> slice: interpretation must become a graph kind with a typed edge to the hypothesis) or **amend
> design rev 8 point 2 to say evidence-line-and-falsification basis.** Do not ship a check whose
> docstring claims a basis it cannot read. *(File as a defect against rev 8.)*

- [ ] **Step 3c: The verdict-agreement GRAPH check** (design rev 8, contract point 2 — *as amended*)

```python
# science/src/science_tool/validate/checks/verdict_agreement.py
"""Does an authored verdict AGREE with the composed evidence? -- at graph time.

`verdict` is an ADJUDICATION, and an adjudication with nothing behind it is a fabrication. The
constraint is NOT conditional on the lifecycle: a `draft` hypothesis asserting `verdict: refuted`
with no basis is exactly as unfounded as a `complete` one.

THREE things this deliberately does NOT do:

1. It does not ORDINALIZE the verdict. `supported|partially-supported|weakened|refuted` is not a
   ladder -- a refuted core member is *expected* under `partially-supported`, `weakened` is
   temporal, and ONE decisive independent test can legitimately establish `refuted`. A
   single-source ceiling applied to `refuted` would flag the strongest possible refutation.
   Compatibility is a MATRIX, not a comparison.
2. It does not FLATTEN member evidence. `belief_for_entity` composes (weakest-link over core
   members) so that strong evidence for one proposition cannot mask a speculative core member.
3. It does not WRITE. It reports a recommendation or a disagreement and never populates or
   overwrites the authored verdict (rev 8 pt. 4). The moment it could, `verdict` would stop being
   an adjudication.

SCOPE -- stated, not assumed. A qualifying basis is an admissible, polarity-agreeing evidence-line
unit, or a `falsification` record, on the hypothesis or one of its CORE members. **Interpretations
are out of scope: `interpretation` is not a graph kind** (the registry has no such entity and no
typed edge to a hypothesis), so rev 8's "or interpretation basis" clause cannot be enforced here.
Do not imply otherwise in a message.
"""

_ORDER = 28
_VERDICTS = ("supported", "partially-supported", "weakened", "refuted")


@Check(section="verdict agreement", order=_ORDER)
def check_verdict_agreement(ctx: ValidateContext) -> Iterator[Result]:
    knowledge, provenance = _load_belief_graphs(ctx)
    if knowledge is None or provenance is None:
        return

    for hyp_uri in _hypotheses(knowledge):
        verdict = next(knowledge.objects(hyp_uri, SCI_NS.verdict), None)
        if verdict is None:
            continue                        # absent == no adjudication recorded. Legal, and common.
        verdict = str(verdict)

        composed = belief_for_entity(knowledge, provenance, hyp_uri, scalar_enabled=...)

        # Direct whole-hypothesis evidence is checked SEPARATELY: when core members exist,
        # belief_for_entity takes the bundle branch and never looks at evidence attached to the
        # hypothesis IRI itself (bundle_belief.py:215+). Bundle dispatch would otherwise HIDE the
        # decisive whole-hypothesis refutation that `verdict.refutation-masked` exists to catch.
        direct = collect_evidence_units(knowledge, provenance, [hyp_uri])

        # NOTE: no `continue`. A missing basis does NOT short-circuit the checks below -- the two
        # findings are INDEPENDENT, and a `supported` hypothesis can lack any supporting basis AND
        # simultaneously mask a decisive refutation. Skipping the invariant for exactly the files
        # with the weakest evidentiary footing would suppress it where it matters most.
        basis = _qualifying_basis(knowledge, provenance, hyp_uri, composed, direct, verdict)
        if not basis:
            yield Result(
                Severity.WARN, _path_for(ctx, hyp_uri), None,
                f"{hyp_uri}: verdict {verdict!r} has no qualifying basis "
                f"(no admissible, polarity-agreeing evidence line or falsification on the "
                f"hypothesis or any core member). A verdict is an adjudication OF something.",
                "verdict.missing-basis", None,
            )

        # THE HARD INVARIANT. `supported` cannot stand on top of an unresolved decisive refutation
        # of the whole hypothesis or of its core conjunction. Note `partially-supported` is NOT
        # included: a refuted member is exactly what that verdict is FOR.
        if verdict == "supported" and _decisive_refutation(composed, direct):
            yield Result(
                Severity.ERROR, _path_for(ctx, hyp_uri), None,
                f"{hyp_uri}: verdict 'supported' with an unresolved decisive refutation of the "
                f"hypothesis or a core member",
                "verdict.refutation-masked", None,
            )

        # Explanatory disagreement -- REPORT ONLY, never a ceiling and never a rewrite.
        if (reason := _disagreement(verdict, composed)) is not None:
            yield Result(
                Severity.WARN, _path_for(ctx, hyp_uri), None,
                f"{hyp_uri}: authored verdict {verdict!r} disagrees with composed belief: {reason}",
                "verdict.disagrees-with-computed", None,
            )
```

**`_qualifying_basis` must establish all three of these — an edge is not a basis:**

| requirement | why `if not units` was not enough |
|---|---|
| **polarity agreement** | a `supports` line is not a basis for `refuted` |
| **admissibility** under the belief policy | a unit the policy excludes is not a basis |
| **located on the hypothesis or a CORE member** | evidence on a *rival*/background member adjudicates nothing about this hypothesis |

**`_disagreement` implements the matrix — it does not compare rungs:**

| verdict | reports a disagreement when… |
|---|---|
| `supported` | the composed belief does not support it (the ERROR case is handled above, separately) |
| `partially-supported` | there is **no** unresolved/disputed/unsupported portion (`unresolved_members` and `contested_members` both empty **and** nothing refuted) — i.e. nothing *partial* about it |
| `weakened` | **no** disputing evidence and no negative adjudication basis. **Never infer a historical trajectory from one snapshot** — a true weakening claim needs a prior `belief_snapshot`; absent one, only report the *absence of any dispute*, never the absence of *change*. |
| `refuted` | no decisive refutation and no linked falsification. **No single-source ceiling** — one decisive independent test is a legitimate refutation. |

- [ ] **Step 3d: Re-gate the hard invariant — and ONLY it.** Add **`verdict.refutation-masked`** to
  the `hygiene` tier in `validate/gates.py`; it inherits the gated ERROR that
  `belief.refutation-masked` held before Task 2b removed it.

  **`verdict.missing-basis` is WARN and ungated** (ruled 2026-07-13 — Task 3b). Not "ERROR, ungated
  for one release": at least 11 of the 15 migrating verdicts **cannot satisfy it**, so an ERROR would
  be an uncertified instrument failing real builds — the original incident, verbatim.

  **`verdict.disagrees-with-computed` is never gated** — a disagreement is information, not a fault.

  Add the regression that keeps the two ratchets apart, because nothing else will:

```python
def test_missing_basis_stays_WARN_even_when_the_KIND_is_certified() -> None:
    # Kind certification and verdict-basis certification are INDEPENDENT facts. `hypothesis` being
    # in _CERTIFIED_KINDS says every root is pinned and renders; it says NOTHING about whether the
    # corpus carries verdict bases (>=11 of 15 do not). Coupling them would let an uncertified rule
    # ride in on a certified one's coattails.
    assert _severity("hypothesis") is Severity.ERROR
    assert severity_of_rule("verdict.missing-basis") is Severity.WARN
    assert "verdict.missing-basis" not in gates.TIERS["hygiene"]
```

- [ ] **Step 4: Green** — unit + wiring, both packages, plus `ruff` and `pyright`.

- [ ] **Step 5: Commit.**

---

## Phase 3 — The `hypothesis` P2m slice (this is where meaning changes)

> **ATOMIC PER KIND, ACROSS ALL 9 REPOS.** `default_profile_for_kind` is **global** — the instant
> Task 9 wires schema validation into the load path, *every* project's hypotheses are validated
> against the new mixin. Rev 1 migrated one repo and expected the other eight to keep validating.
> **They cannot.** Two options existed; this is the one taken:
>
> **A per-project version pin.** `science.yaml` gains `entity_schema_version: 2`. The load path
> selects the hypothesis mixin **only** for pinned projects; unpinned projects keep today's
> behaviour (no schema validation for `hypothesis`, WARN-only vocabulary check). The migration
> command **sets the pin as its final act**, atomically with the file rewrites. So each *project*
> migrates atomically, and the *kind* is migrated when all 18 roots are pinned (Task 11's ratchet
> requires exactly that).
>
> **This is not the forbidden compatibility layer.** That layer is code that *guesses* which
> meaning a file carries. This is an **authored declaration** of which version a project is on —
> which is precisely what D5 means by "introduce target schema versions." The difference is that
> nothing here infers anything.

### Task 8: Descriptor, model, template — and the version pin

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py:32-51`
- Modify: `science/model/src/science_model/entities.py:797-839` (`HypothesisEntity`)
- Modify: `science/src/science_tool/entities.py` (`_LIVE_STATUSES`)
- Modify: `science/model/src/science_model/templates/hypothesis.md` **and** `templates/hypothesis.md` — **two copies; the packaged one is what the Renderer reads**
- Modify: the `science.yaml` schema to admit `entity_schema_version: int`
- Test: `science/model/tests/test_hypothesis_entity.py`

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_hypothesis_entity.py
from science_model.entities import HypothesisEntity
from science_model.profiles.core import CORE_PROFILE


def _kind():
    return next(k for k in CORE_PROFILE.entity_kinds if k.name == "hypothesis")


def test_descriptor_declares_the_lifecycle_not_the_verdict() -> None:
    assert sorted(_kind().statuses) == sorted(
        ["draft", "active", "complete", "superseded", "retired", "archived"]
    )
    assert _kind().default_status == "active"


def test_verdict_and_closure_basis_are_first_class_fields() -> None:
    h = HypothesisEntity(id="hypothesis:1", kind="hypothesis", title="T", project="p",
                         status="active", verdict="refuted")
    assert h.verdict == "refuted"


def test_disposition_is_gone() -> None:
    assert "disposition" not in HypothesisEntity.model_fields
    assert "disposition_basis" not in HypothesisEntity.model_fields


def test_the_projection_does_NOT_reimplement_the_schema_invariants() -> None:
    # D3: JSON Schema is THE authority; Pydantic is a PROJECTION. Rev 1 duplicated
    # `complete requires a verdict` as a model_validator -- which recreates the second
    # authority D3 exists to abolish, and guarantees the two eventually disagree. The
    # projection must be able to REPRESENT anything the schema admits, and must not
    # independently police it. `test_schema_and_projection_agree` is what keeps them honest.
    HypothesisEntity(id="hypothesis:1", kind="hypothesis", title="T", project="p",
                     status="complete")  # no verdict -- the SCHEMA rejects this, not Pydantic


def test_schema_and_projection_agree() -> None:
    # D3 point 4: the CI reconciliation check. This REPLACES the duplicated validators.
    import json
    from importlib.resources import files

    schema = json.loads(
        (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
    )
    for field in ("status", "verdict", "closure_basis"):
        assert field in HypothesisEntity.model_fields, f"{field} declared in schema, absent from projection"
    descriptor = next(k for k in CORE_PROFILE.entity_kinds if k.name == "hypothesis")
    assert sorted(schema["properties"]["status"]["enum"]) == sorted(descriptor.statuses)
```

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Rewrite the descriptor** (`profiles/core.py`):

```python
        EntityKind(
            name="hypothesis",
            canonical_prefix="hypothesis",
            layer="layer/core",
            description="Testable project hypothesis.",
            entity_class=EntityClass.EPISTEMIC,
            category=KindCategory.AUTHORED_CORE,
            template_ready=True,
            shortform="h",
            home="entities/hypotheses",
            strategy="numeric",
            # `status` is the LIFECYCLE, uniformly, on every kind. The old vocabulary
            # (proposed | under-investigation | partially-supported | supported | weakened |
            # refuted | archived) was the epistemic VERDICT wearing the lifecycle's name --
            # which left `archived` as the only lifecycle word a hypothesis had, and pushed
            # authors into hand-rolling `phase` for the rest. The verdict now lives in
            # `verdict`; `phase` folds in here (design rev 7).
            default_status="active",
            statuses=["draft", "active", "complete", "superseded", "retired", "archived"],
        ),
```

> **`archived` must stay.** `consolidate._is_consolidatable` (`consolidate.py:44-49`) returns
> False for a closed vocabulary lacking `archived` — dropping it silently breaks hypothesis
> consolidation.

**Step 3b — `HypothesisEntity`.** Fields only. **No `model_validator`s re-implementing the schema.**

```python
class HypothesisEntity(ProjectEntity):
    """Hypothesis — two orthogonal axes, in two fields.

    `status` (inherited) is the LIFECYCLE. `verdict` is the EPISTEMIC conclusion. Neither may
    be inferred from the other, and the cell that proves it is `superseded` + `supported` —
    formerly supported, now replaced — which the collapsed field could not express at all:
    writing `superseded` OVERWROTE `supported` and destroyed the conclusion.

    `verdict` is ABSENT until the evidence speaks. That absence is load-bearing, and it is why
    `proposed`/`under-investigation` are not verdict values: they say the evidence has NOT
    spoken, which absence already says.

    THE INVARIANTS ARE NOT HERE. `complete` requires a verdict; `retired` requires a
    closure_basis; `superseded` requires lineage or a basis. All three live in
    `mixin-hypothesis-1.0.json`, which is the sole authority (D3). Re-asserting them as
    model_validators would build the second authority D3 abolishes, and the two would drift.
    `test_schema_and_projection_agree` is the gate that keeps this class honest instead.
    """

    verdict: Literal["partially-supported", "supported", "weakened", "refuted"] | None = None
    closure_basis: str | None = None
    superseded_by: str | None = None
    resynthesized_into: list[str] = Field(default_factory=list)
    archive_ref: str | None = None
```

**Step 3c — `_LIVE_STATUSES`** (`science/src/science_tool/entities.py:193-243`): remove the six
verdict words **only if no other kind still declares them**:

```bash
cd science && rg -n '"(proposed|under-investigation|partially-supported|supported|weakened|refuted)"' ../science/model/src/science_model/profiles/
```

`draft`/`active`/`complete`/`retired` are already LIVE; `superseded`/`archived` are HIDDEN. The
guard `test_every_declared_status_still_classified` fails loud if this is wrong — **let it drive.**

**Step 3d — the templates** (both copies): `status: "active"`, delete `phase:`, delete
`disposition:`/`disposition_basis:`, delete both from `_template.frontmatter`.

**Step 3e — `science.yaml`:** admit `entity_schema_version: int | None`. Absent ⇒ version 1
(unmigrated). No project sets it yet — Task 9 does that per repo.

- [ ] **Step 4: Green — both suites, plus ruff and pyright.** Consumers that read the old
  vocabulary are updated in **Task 10**, so run Task 10's edits together with this task's if the
  suite is red at this point. **Do not commit red** (rev 1 explicitly told the implementer to,
  which is both a broken task and a contradiction of its own atomicity claim).

- [ ] **Step 5: Commit.**

---

### Task 9: The migration — two-phase, all-or-none, per repo

**Files:**
- Create: `science/src/science_tool/migrate_hypothesis.py`
- Modify: `science/src/science_tool/entities_cli.py` (register `entity migrate-hypothesis`)
- Test: `science/tests/test_migrate_hypothesis.py`

**Interfaces:**
- Consumes `status_inventory.inventory()` + `load_adjudication()`. **Adds no mapping logic.**

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_migrate_hypothesis.py
def test_refuses_everything_when_any_file_is_ambiguous(tmp_path) -> None:
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")     # deterministic
    _hyp(tmp_path, "0009-d", status="retired", phase="candidate")   # ambiguous
    with pytest.raises(MigrationRefused, match="0009-d"):
        migrate(tmp_path, apply=True)
    assert 'status: "proposed"' in (tmp_path / "entities/hypotheses/0001-a.md").read_text()


def test_an_adjudication_file_unblocks_it(tmp_path) -> None:
    _hyp(tmp_path, "0009-d", status="retired", phase="candidate")
    (tmp_path / ".science").mkdir()
    (tmp_path / ".science/hypothesis-lifecycle.adjudication.yaml").write_text(
        'hypothesis:0009-d:\n  status: retired\n  verdict: weakened\n'
        '  closure_basis: "confirmatory null, z=-0.889"\n', encoding="utf-8")
    migrate(tmp_path, apply=True)
    t = (tmp_path / "entities/hypotheses/0009-d.md").read_text()
    assert 'status: "retired"' in t and 'verdict: "weakened"' in t and "z=-0.889" in t


def test_NOTHING_is_written_if_any_target_fails_schema_validation(tmp_path, monkeypatch) -> None:
    # TWO-PHASE. Rev 1 wrote files in a loop, so an I/O or render failure on file 90 left 89
    # migrated and 58 not -- a corpus with two meanings of `status` live at once, which is
    # exactly the state that forces the compatibility layer D5 forbids.
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    _hyp(tmp_path, "0002-b", status="proposed", phase="active")
    monkeypatch.setattr("science_tool.migrate_hypothesis._render", _boom_on("0002-b"))
    with pytest.raises(MigrationRefused):
        migrate(tmp_path, apply=True)
    assert 'status: "proposed"' in (tmp_path / "entities/hypotheses/0001-a.md").read_text()


def test_sets_the_version_pin_as_its_final_act(tmp_path) -> None:
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    migrate(tmp_path, apply=True)
    assert "entity_schema_version: 2" in (tmp_path / "science.yaml").read_text()


def test_dry_run_writes_nothing(tmp_path) -> None:
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    before = (tmp_path / "entities/hypotheses/0001-a.md").read_text()
    migrate(tmp_path, apply=False)
    assert (tmp_path / "entities/hypotheses/0001-a.md").read_text() == before


def test_body_and_unrelated_frontmatter_survive(tmp_path) -> None:
    _hyp(tmp_path, "0001-a", status="proposed", phase="active",
         extra={"source_refs": ["paper:Smith2020"]}, body="## Rationale\n\nkeep me.")
    migrate(tmp_path, apply=True)
    t = (tmp_path / "entities/hypotheses/0001-a.md").read_text()
    assert "paper:Smith2020" in t and "keep me." in t
```

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Implement — render + validate EVERYTHING, then write**

```python
# science/src/science_tool/migrate_hypothesis.py
"""Migrate hypothesis `status`/`phase` -> `status` (lifecycle) + `verdict` (epistemic).

TWO-PHASE AND ALL-OR-NONE. Every target is rendered AND schema-validated before a single byte
is written. A half-migrated corpus carries two incompatible meanings of `status` at once, and
the only way to serve both is the heuristic compatibility layer the design forbids -- so a
failure partway through the write loop would manufacture exactly the state this whole arc
exists to eliminate.

The mapping lives in `status_inventory`, entirely and deliberately. This module applies what
the planner decided and adds no rule of its own: a rule that lived here and not there would
mean the inventory a human read and approved was not the migration that ran.
"""

from __future__ import annotations

from pathlib import Path

from science_model.entity_schema import (
    EntityValidationError, EntityValidator, default_profile_for_kind,
)
from science_model.frontmatter import atomic_write_text, render_frontmatter, split_frontmatter

from science_tool.status_inventory import inventory, load_adjudication

ADJUDICATION_PATH = Path(".science/hypothesis-lifecycle.adjudication.yaml")
_DROPPED = ("phase", "disposition", "disposition_basis", "profile")


class MigrationRefused(Exception):
    """Raised when the corpus cannot be migrated. NOTHING has been written."""


def _render(path: Path, row) -> tuple[Path, str, dict]:
    fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
    fm["status"] = row.target_status
    if row.target_verdict is not None:
        fm["verdict"] = row.target_verdict
    if row.target_closure_basis is not None:
        fm["closure_basis"] = row.target_closure_basis
    for key in _DROPPED:
        fm.pop(key, None)
    return path, render_frontmatter(fm, body), fm


def migrate(project_root: Path, *, apply: bool) -> list[Path]:
    adjudication = load_adjudication(project_root / ADJUDICATION_PATH)
    inv = inventory(project_root, adjudication=adjudication)

    if inv.ambiguous:
        lines = [
            f"{len(inv.ambiguous)} hypothesis file(s) need an author's decision. "
            f"NOTHING has been written.",
            "",
        ]
        for row in inv.ambiguous:
            lines += [f"  {row.path}",
                      f"      status={row.status!r} phase={row.phase!r}",
                      f"      {row.ambiguity}", ""]
        lines.append(
            f"Record each decision in {ADJUDICATION_PATH} (status, verdict, closure_basis) "
            f"and re-run. Do NOT guess: a terminal status has already destroyed the prior "
            f"verdict, and inventing one would fabricate an epistemic conclusion."
        )
        raise MigrationRefused("\n".join(lines))

    # PHASE 1 -- render and validate EVERY target. No writes.
    validator = EntityValidator()
    profile = default_profile_for_kind("hypothesis")
    planned: list[tuple[Path, str]] = []
    failures: list[str] = []
    for row in inv.deterministic:
        try:
            path, text, fm = _render(row.path, row)
        except Exception as exc:  # render failure -- refuse the whole corpus
            failures.append(f"{row.path}: could not render: {exc}")
            continue
        try:
            validator.validate_as(fm, profile)
        except EntityValidationError as exc:
            failures.append(f"{row.path}: migrated form fails its own schema: {exc}")
            continue
        planned.append((path, text))

    if failures:
        raise MigrationRefused(
            "The migrated corpus would not satisfy its own schema. NOTHING has been "
            "written.\n\n" + "\n".join(f"  {f}" for f in failures)
        )

    if not apply:
        return [p for p, _ in planned]

    # PHASE 2 -- write. Every target is already rendered and schema-valid.
    for path, text in planned:
        atomic_write_text(path, text)

    # The version pin, LAST: a project is on schema 2 only once its files actually are.
    _set_entity_schema_version(project_root, 2)
    return [p for p, _ in planned]
```

> `_set_entity_schema_version` writes `entity_schema_version: 2` into `science.yaml`. It is the
> **final** act: a crash before it leaves the project unpinned, and unpinned means "not schema-2",
> so re-running is safe and idempotent.

- [ ] **Step 4: Green** — `6 passed`.

- [ ] **Step 5: Commit.**

---

### Task 10: Consumers — and **only** the hypothesis branch

**Files:**
- `science/src/science_tool/hypotheses_cli.py:28-34,62-64` — `--phase` → `--status`; the `promotion-criteria` section now triggers on `status == "draft"`
- `science/src/science_tool/entities_cli.py:94-125` — add `--verdict`, `--closure-basis`, `--superseded-by`
- `science/src/science_tool/entities.py:935-969` (`edit_entity`) — **the lifecycle boundary**
- `science/src/science_tool/entities.py:1377-1379` (`_validate_status`) — also fix its raw `KeyError` (it indexes `_STATUS_VALUES[kind]` and ignores project-local manifests, unlike `valid_statuses`)
- `science/src/science_tool/graph/materialize.py` — emit `sci:verdict`; **delete** `sci:disposition`
- `science/src/science_tool/graph/attention.py:125-137` — delete the `sci:disposition` terminal-exclusion; use the lifecycle instead
- `science/src/science_tool/validate/checks/dataset_capabilities.py:24-54` — **hypothesis branch only**
- `science/src/science_tool/validate/checks/hypotheses.py:23,64-70,127-136` — delete the `phase` check
- `science/src/science_tool/annotation/promote.py:330-331` — `fields["phase"] = "candidate"` → `fields["status"] = "draft"`
- `commands/big-picture.md:62,213-217` · `commands/add-hypothesis.md:124`

> ### ⛔ DO NOT TOUCH `DEBT_QUESTION_STATUSES`
> Rev 1 rewrote `is_question_debt` to take an `answer_state` — **while questions still encode
> answeredness in `status`, because `question` is a later slice.** That would have silently
> changed which questions count as debt: a live `status: partially-answered` would stop counting
> (it is not in `{active, deferred}` and has no `answer_state`), and `status: answered` would stop
> suppressing demand warnings. **A consumer may only be rewritten in its own kind's slice.**
> `attention.py:25-27` stays exactly as it is until the `question` slice.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_hypothesis_consumers.py
def test_demand_closed_reads_the_hypothesis_VERDICT_now() -> None:
    # `refuted` was the ONLY hypothesis-specific value any consumer read
    # (dataset_capabilities.py:46). It is a verdict now, not a status.
    assert is_demand_closed(kind="hypothesis", status="active", verdict="refuted") is True
    assert is_demand_closed(kind="hypothesis", status="active", verdict="supported") is False
    assert is_demand_closed(kind="hypothesis", status="retired", verdict=None) is True


def test_QUESTION_demand_closure_is_UNCHANGED() -> None:
    # The question slice has not happened. Its statuses still carry answeredness, and this
    # predicate must keep reading them exactly as it does today.
    assert is_demand_closed(kind="question", status="answered", verdict=None) is True
    assert is_demand_closed(kind="question", status="active", verdict=None) is False


def test_question_debt_is_untouched() -> None:
    from science_tool.graph.attention import DEBT_QUESTION_STATUSES
    assert DEBT_QUESTION_STATUSES == frozenset({"active", "partially-answered", "deferred"})


def test_edit_status_is_the_lifecycle_boundary(tmp_project) -> None:
    # One generic boundary, not four invented verbs (design §9 D4). It schema-validates the
    # target, takes --closure-basis ATOMICALLY with the transition, and FAILS BEFORE WRITING.
    with pytest.raises(EntityCommandError, match="closure_basis"):
        edit_entity(tmp_project, "hypothesis:0001-x", status="retired")
    assert 'status: "active"' in (tmp_project / "entities/hypotheses/0001-x.md").read_text()

    edit_entity(tmp_project, "hypothesis:0001-x", status="retired", closure_basis="no samples")
    t = (tmp_project / "entities/hypotheses/0001-x.md").read_text()
    assert 'status: "retired"' in t and 'closure_basis: "no samples"' in t
```

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Implement.** `dataset_capabilities` — change **only** the hypothesis branch:

```python
# questions still carry answeredness in `status` -- the question slice has not run.
_QUESTION_CLOSED = frozenset({"answered", "resolved", "closed", "rejected", "duplicate"})
_CLOSED_LIFECYCLE = frozenset({"superseded", "retired", "archived", "complete",
                               "abandoned", "deprecated"})


def is_demand_closed(*, kind: str, status: str | None, verdict: str | None = None) -> bool:
    """Whether a question/hypothesis still exerts live pull on data.

    Deliberately conservative -- a suppressor should fail toward KEEPING the warning, since a
    false-suppress hides a real coverage gap while a false-keep leaves only a low-value
    warning. So `supported` (can still be strengthened) and `weakened` (verdict still open)
    keep warning; only `refuted` settles the demand.
    """
    if status in _CLOSED_LIFECYCLE:
        return True
    if kind == "hypothesis":
        return verdict == "refuted"          # <- the ONLY change in this slice
    return status in _QUESTION_CLOSED        # <- questions: UNCHANGED
```

`edit_entity` — the generic lifecycle boundary (D4):

```python
def edit_entity(
    project_root: Path, ref: str, *,
    title: str | None = None, status: str | None = None,
    verdict: str | None = None, closure_basis: str | None = None,
    superseded_by: str | None = None,
    related: list[str] | None = None, source_refs: list[str] | None = None,
    updated: date | None = None, today: date | None = None,
) -> EntityWriteResult:
    project_root = project_root.resolve()
    _reject_if_archived(project_root, ref)
    location = find_entity(project_root, ref)
    frontmatter = dict(location.frontmatter)

    if title is not None:
        frontmatter["title"] = title
    if status is not None:
        frontmatter["status"] = status
    if verdict is not None:
        frontmatter["verdict"] = verdict
    if closure_basis is not None:
        frontmatter["closure_basis"] = closure_basis
    if superseded_by is not None:
        frontmatter["superseded_by"] = superseded_by
    if related:
        frontmatter["related"] = _append_unique_string_values(frontmatter.get("related"), related)
    if source_refs:
        frontmatter["source_refs"] = _append_unique_string_values(
            frontmatter.get("source_refs"), source_refs
        )
    frontmatter["updated"] = (updated or today or date.today()).isoformat()

    # THE lifecycle boundary. The composed schema is the authority, so a terminal transition
    # missing its basis fails HERE -- before a byte is written -- rather than landing on disk
    # and surfacing as a validate WARN later. `--closure-basis` is accepted ATOMICALLY with
    # the transition precisely so this can be a single check.
    _schema_validate_or_raise(project_root, location.kind, frontmatter)
    _resolution_check_or_raise(project_root, frontmatter)   # Task 7's cross-record layer

    text = _render_markdown(frontmatter, location.body)
    warnings = _validate_prospective_write(
        project_root=project_root, rel_path=Path(location.rel_path),
        text=text, target_entity_id=location.entity_id,
    )
    _atomic_replace_text(location.path, text)
    return EntityWriteResult(entity_id=location.entity_id, path=location.path, warnings=warnings)
```

where `_schema_validate_or_raise` derives the profile via `default_profile_for_kind`, **skips
kinds not yet in `PROJECT_MIXIN_NAMES`** (an explicit "not migrated", not a fallback), and
re-raises `EntityValidationError` as `EntityCommandError`.

- [ ] **Step 4: Green — everything, both packages, ruff, pyright.**

- [ ] **Step 5: Commit.**

---

### Task 11: Roll out across every project that authors a hypothesis, with a graph diff

> **The roster is DERIVED, not listed** (see the rev-4 correction at the top). Rev 1–3 hardcoded
> nine repos and would have migrated **85 of 147** hypotheses, leaving 62 on the old meaning while
> `default_profile_for_kind` flipped globally — the exact non-atomic split this whole phase exists
> to prevent. Re-derive at execution time; do not trust the table, and do not trust this list either
> if the corpus has moved since.

> ### Three distinctions this task previously collapsed (ruled 2026-07-12)
>
> **A root is not a repo.** 18 roots live in **15 git repositories**: `science/meta` and the three
> `science/tests/fixtures/**` roots all share `~/d/science`. Commit grouping must derive from
> `git rev-parse --show-toplevel`, **never from the root path** — otherwise this task tries to make
> four commits in one repo and the last three see a dirty tree they did not create.
>
> **The fixtures are schema-contract participants, not test data.** They are pinned with everything
> else; leaving them unpinned would make the suite assert an *accidental mixed-version* state and
> call it passing. Coverage of intentionally-unpinned/old-version behaviour is preserved by
> **constructing dedicated temporary projects in the test**, never by leaving a canonical fixture
> stale. And the missing-status canary gets an **explicit adjudication entry** like any other file —
> fixtures get no inference shortcut.
>
> **`cancer/mechanisms/evolution` is a hard gate, not a late chore.** It must participate in Task 2
> adjudication, Task 2b's regression test, Task 6b's extension validation, the global render
> validation, the migration, the graph diff, and the ratchet. It owns all 13 belief-cluster files:
> it is the corpus most capable of **refuting** this migration, so it must never be the corpus that
> validates last.

- [ ] **Step 0: Derive the roster AND write the manifest.** Later steps consume the file; a step
  that only prints is a step whose output the next step cannot check. Symlinks (`~/d/r/*`) must
  collapse via `.resolve()` or a repo migrates twice.

```bash
uv run python - <<'PY'
import json, subprocess
from pathlib import Path
from science_tool.field_inventory import field_inventory

D = Path.home() / "d"
SKIP = {".venv", ".git", ".claude", ".worktrees", "node_modules", "templates"}
roots = sorted({
    p.parent.resolve()                      # .resolve() collapses the ~/d/r/* symlinks
    for p in D.glob("**/science.yaml")
    if not any(s in SKIP for s in p.parts) and "--" not in p.parent.name
})
manifest = []
for r in roots:
    n = field_inventory(r, "hypothesis").get("id", 0)
    if not n:
        continue
    top = subprocess.run(["git", "-C", str(r), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, check=True).stdout.strip()
    manifest.append({"root": str(r), "n": n, "repo": top,
                     "slug": str(r.relative_to(D)).replace("/", "-")})   # UNIQUE: full rel path
manifest.sort(key=lambda m: m["root"])
Path("/tmp/claude-1000/roster.json").write_text(json.dumps(manifest, indent=2))
repos = {m["repo"] for m in manifest}
print(f"{len(manifest)} roots, {sum(m['n'] for m in manifest)} hypotheses, {len(repos)} git repos")
PY
```

Expect **18 roots / 147 hypotheses / 15 git repos** as of 2026-07-12.

> **The gate is set equality on `(root, n)` — not the totals.** `18/147` is satisfiable while a
> root silently disappears and another gains the same count. Snapshot the manifest **once**, here,
> and require **exact equality** against a freshly derived one immediately before *apply* (Step 1)
> and again before the *ratchet* (Task 12). Any diff ⇒ the corpus moved under a certification that
> was measured against exactly these 147 files. **Stop and re-certify; do not reconcile in place.**

- [ ] **Step 1: Two-phase preflight over ALL 147 targets — render and validate everything, then
  write.** No root is applied until every root's rendered target has passed. This is what makes the
  slice atomic across 15 repositories rather than merely ordered.

```bash
uv run science entity migrate-hypothesis --preflight-all --manifest /tmp/claude-1000/roster.json
```

- **Preflight must include `cancer/mechanisms/evolution`.** It is the only root where Task 2b's
  deletion and Task 6b's `evidence_scope` extension actually bite.
- **With a green all-corpus preflight, apply order is free** — take smallest-first
  (`pre-cancer` (1) …) so a surprise is cheapest.
- **If you ever fall back to per-root validate-then-write, apply `evolution` FIRST.** Ordering by
  size would leave the most refutation-capable corpus for last, after 14 repos are already written.

For each root (order per above):

```bash
SLUG=$(...)                                          # from the manifest -- NOT basename $PWD:
                                                     # science/meta and health/meta both basename
                                                     # to "meta" and would clobber each other's .trig
cd "$ROOT"
uv run science graph build --output /tmp/claude-1000/before-$SLUG.trig
uv run science entity status-inventory               # 0 refused, or adjudicate first
uv run science entity migrate-hypothesis --apply     # two-phase; sets entity_schema_version: 2
uv run science graph build --output /tmp/claude-1000/after-$SLUG.trig
uv run science validate; echo "exit=$?"              # MUST be 0
```

> **Task 2b must be merged before `evolution` is written**, in either ordering. It is the repo where
> a field-order mistake silently promotes 13 hypotheses `speculative` → `supported`.

- [ ] **Step 2: Diff the graph and account for every triple.** Expected, and nothing else:
  - `sci:projectStatus` values change per the rev-7 mapping
  - **new** `sci:verdict` triples on exactly the hypotheses that carry one
  - **zero** `sci:disposition` triples before **and** after (never authored)
  - **no** `phase` triples in either (it never reached the graph — `Entity` is `extra="ignore"`)
  - **no** change to any non-hypothesis subject

  **Any unexplained triple means the slice is not atomic. Stop and find it.**

- [ ] **Step 3: With every root pinned, re-derive and validate the whole roster.**

```bash
uv run python - <<'PY'
import json, subprocess
from pathlib import Path
manifest = json.loads(Path("/tmp/claude-1000/roster.json").read_text())
for m in manifest:
    r = subprocess.run(["uv", "run", "science", "validate"], cwd=m["root"], capture_output=True)
    print(f"exit={r.returncode}  {m['root']}")
PY
cd ~/d/science/science && uv run --frozen pytest -q   # the 3 fixture roots live in THIS repo
```
**Every root exits 0, and our own suite is green.** This is the step whose absence caused the
original incident — and rev 1–3 would have run it over 58% of the corpus and called it clean.

- [ ] **Step 4: Commit per GIT REPOSITORY — 15 commits, not 18.**

```bash
uv run python -c "
import json; from pathlib import Path
m = json.loads(Path('/tmp/claude-1000/roster.json').read_text())
repos = {}
for e in m: repos.setdefault(e['repo'], []).append(e['root'])
for repo, roots in sorted(repos.items()): print(repo, '<-', len(roots), 'root(s)')"
```

`~/d/science` holds **four** roots (`science/meta` + the three fixtures). Committing per *root*
would attempt four commits in one repository, and commits 2–4 would sweep up the other roots'
changes as an unexplained dirty tree. **Group by `repo`, commit once per repo.**

`r/mm30` and `r/cbioportal` are **symlinks** — `.resolve()` already collapsed them, so they
cannot produce a duplicate repo. Several repos are **Dropbox-only with no remote — do not push.**

---

## Phase 4 — The ratchet

### Task 12: `hypothesis` → ERROR

- [ ] **Step 1: Write the failing test**

```python
def test_severity_is_a_property_of_the_KIND() -> None:
    # The original incident: severity graded on `layout_version >= 3`. All five projects were
    # v3, so the gate graded NOTHING and 472 entities errored the moment the check landed.
    assert _severity("hypothesis") is Severity.ERROR   # sources AND consumers certified
    assert _severity("report") is Severity.WARN        # not migrated
    assert _severity("question") is Severity.WARN
```

- [ ] **Step 2: Implement**

```python
# A kind joins this set at the END of its P2m slice -- never before. An uncertified
# instrument may not fail anyone's build.
#
# THIS SET CERTIFIES THE KIND, NOT EVERY RULE ABOUT IT. `hypothesis` here means: all 18 roots are
# pinned, render, and validate. It does NOT mean the corpus carries verdict BASES -- >=11 of the 15
# migrating verdicts do not, so `verdict.missing-basis` has its OWN ratchet and stays WARN. Two
# independent facts; do not let one certify the other.
_CERTIFIED_KINDS: frozenset[str] = frozenset({"hypothesis"})


def _severity(kind: str) -> Severity:
    return Severity.ERROR if kind in _CERTIFIED_KINDS else Severity.WARN
```

- [ ] **Step 3: Re-assert the manifest, then validate.** Re-derive the roster and require **exact
  `(root, n)` set equality** against `/tmp/claude-1000/roster.json` (Task 11 Step 0). Totals are not
  a gate: `18/147` still holds if one root vanishes while another gains the same count. Only then
  run `science validate` across all 18 roots — **all exit 0** — plus our own suite for the three
  fixture roots. Flipping `hypothesis` to ERROR against a corpus that has drifted since
  certification is precisely the original incident.
- [ ] **Step 4: Commit** (15 repos, grouped by `git rev-parse --show-toplevel`).

> ### Out of scope: the verdict-basis ratchet (deferred, not forgotten)
>
> **`verdict.missing-basis` does NOT flip here.** It is a *rule*-level ratchet, and its precondition
> is a different fact about a different thing: **`science validate` emitting zero
> `verdict.missing-basis` findings across all 18 roots** — as reported by the **shipped validator**,
> never by Task 3b's surrogate unit count (the sweep bounds the deficit at **≥11, ≤15**; only
> `_qualifying_basis` can adjudicate polarity, admissibility, and core-member scope).
>
> That precondition is **research work**: authoring the evidence-lines and falsifications that 11+
> real adjudications currently rest on only in their authors' heads. It is the *content* of D5's
> follow-through, and it is what makes `verdict` mean anything. When it is done, this same Step 3
> discipline applies to it — **re-assert the manifest, then check the instrument's own output.**

## What rev 3 got wrong (caught by Task 1, its own first instrument)

13. **Every rev carried a roster that contradicted its own total, and no rev added it up.** "147
    hypotheses in **9 repos**", followed by nine per-repo counts summing to **85**. The two numbers
    sat in a single sentence from rev 1 through rev 3. A second tell was equally public: the
    cross-tab needs ≥96 files carrying `phase` (60 `active` + 36 `candidate`), but the 9-repo
    inventory finds only 64. **Neither required new data to catch — only arithmetic on data already
    in the document.**
14. **The corpus claims were certified; the roster was not.** The `147`, the cross-tab and the
    36 keys were all measured across `~/d`. The **repo list** was typed by hand — and it was the
    only one of those artifacts that Task 11 would have *executed*. So the plan's most-verified
    numbers guarded its least-verified one, and the mismatch read as detail rather than defect.
15. **The consequence was precisely the non-atomicity the phase exists to prevent.** Migrating the
    nine would have moved 85 of 147 files while `default_profile_for_kind` flipped **globally** —
    62 hypotheses left on the old meaning, in projects nobody was watching, with `validate` green
    across all nine and the slice declared done. That is finding #6 (rev 1's cross-project defect)
    **reintroduced through the data instead of the code**: rev 2 fixed the *mechanism* (a per-project
    `entity_schema_version` pin) and left the *scope* uncertified.
16. **And the headline defect was outside the rollout entirely.** All 13 `belief_state` /
    `evidence_stance` / `author_stated_evidence` files — design rev 8's belief ruling, Task 2b's
    `speculative` → `supported` corruption — live in `cancer/mechanisms/evolution`, which the plan
    never listed. **Two `~/d/r/*` entries were symlinks** into `cancer/`, so the plan also counted
    two repos twice and would have graph-diffed them against themselves.

> **The lesson, and it is the same one twice:** *a scope that is **listed** has a hole by
> construction; derive it.* Phase 6's import guard taught this about code. Task 1 just taught it
> about **corpora** — and the instrument only caught it because it globbed `science.yaml` instead of
> reading the list it was handed. **Certify the population, not just the measurement.**

## What rev 2 got wrong (ruled in design rev 8)

9. **It used "observed somewhere" as the admission rule for the core mixin.** Every declared corpus
   key went into the global `mixin-hypothesis` — so mm30's `confidence_mechanistic_label` would have
   become a **core Science field for all 22 projects** because one project authored it. That is
   design §6's ownership contract, violated. **Ownership is a scope**, and the inventory now decides
   it per key: core · project-extension · rename/migrate · derived/delete. Task 6b composes the
   extensions, and it is a **hard prerequisite for strictness** — closing the schema without it
   leaves exactly two options, both wrong: reject mm30's files, or promote its fields to core.
10. **It treated six unrelated fields as one "belief cluster"** and asked one question about all six.
    They are **three different ownership patterns**: `belief_state` is the second-source-of-truth
    defect (**delete** — hypothesis belief is already computed); `evidence_stance` /
    `author_stated_evidence` are **provenance, not magnitude**; `confidence_*label` are **real MM
    interface fields** belonging in a project extension. Asking one question about six fields was
    itself the error — it hid the partition.
11. **It scoped verdict-has-evidence to `status: complete`.** Wrong: **every** authored verdict needs
    a basis. A `draft` hypothesis asserting `refuted` with no evidence is exactly as unfounded as a
    `complete` one, and the `complete` gate would have left the front door open.
12. **And it nearly shipped a silent corruption.** Removing `belief_state` (correctly) would have
    promoted **13 hypotheses from `speculative` to `supported`** — because `_authored_magnitude`
    returns on the **first recognized field**, and those same 13 files carry
    `evidence_stance: literature-supported`, which the ladder maps to `supported`. The fix is to
    **delete the fallback chain, not adapt it**: provenance must never set an epistemic magnitude.
    **A field-order dependency is a collapsed axis wearing a different hat** — and I would have
    walked into one while cleaning up the last one.

## What rev 1 got wrong

Recorded because three of these were **phasing** errors, and phasing errors are the ones that
survive review by looking like schedule rather than substance.

1. **It skipped P0.** The design says *inventory and declare every field, then migrate values*.
   Rev 1 went straight to the value migration and declared ~15 fields against a **36-key** real
   vocabulary. `unevaluatedProperties: false` would have rejected `required_capabilities` (38
   files), `lens_views` (28), and 18 more. Phase 0 exists now.
2. **Its strictness test proved nothing.** It asserted that `phase` is rejected — but `phase` is
   explicitly `false` in the schema. It never tested an *arbitrary* unknown key, which is the
   actual defect (`extra="ignore"` silently dropping undeclared keys).
3. **It would have validated the enriched dict.** `_enrich_raw` (`sources.py:713`) injects
   `project`, `canonical_id`, `profile`, `type`, `aliases`, `content_preview` **before** Pydantic
   sees a record. Closing the schema over that would have declared six fields no author ever wrote.
4. **Its migration could not escape its own refusal.** The refusal said *"fix the file and re-run"* —
   but the classifier re-reads the same terminal `status` and refuses again, forever. `0009` had
   **no path through**. An adjudication artifact fixes it; inferring from file shape cannot.
5. **Its migration was not transactional.** A `write_text` loop leaves a half-migrated corpus on
   any failure — two meanings of `status` live at once, the exact state that forces the forbidden
   compatibility layer. Now: render + schema-validate **everything**, then write.
6. **It migrated one repo and expected eight others to keep working.** `default_profile_for_kind`
   is global; wiring it flips every project at once. There are **18 project roots** and 147 files. Fixed by
   an explicit per-project `entity_schema_version` pin — a *declaration*, not a heuristic.
7. **It rebuilt the second authority D3 abolishes.** It duplicated `complete requires a verdict`
   as a Pydantic `model_validator` alongside the JSON Schema `if/then`. Two authorities always
   drift. Replaced by a **reconciliation test**.
8. **It admitted, in its own self-review, that `check_resolution` was never wired** — and shipped
   anyway. Presence enforced, resolution not: the dangling-`superseded_by` hole, reopened by the
   very task written to close it.

**The pattern:** rev 1 reasoned about the *design* and never about the *corpus* or the *call
graph*. Exactly the failure rev 7 of the design caught in itself — and I repeated it one document
later.

## What this plan does NOT do

- **The other 32 kinds.** This builds the machinery and migrates **one**. `question` is the
  natural second (the only kind whose status values actually drive behaviour) — and its consumers
  are deliberately **untouched** here.
- **P1 (absorb `provided_capabilities`/`required_capabilities`).** Declared in the mixin, not
  absorbed.
- **`science:graph` / `science:axis`** (design §3, §5). Not needed to migrate `hypothesis`.
- **The 6 filed defects**, notably **`fb-2026-07-12-006`: every commons dataset is on a crashing
  overlay path today.** Independent of this arc; worth fixing sooner.
- **The 169 residual status-vocabulary WARNs** on other kinds. They stay WARNs until their slices.

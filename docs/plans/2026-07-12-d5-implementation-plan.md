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

0. ### ☠️ EVERY `science` COMMAND RUN INSIDE A CONSUMER MUST NAME THIS WORKTREE
   Consumer projects install the toolkit from the **public Git source**, revision pinned in their
   `uv.lock`:
   ```toml
   [tool.uv.sources]
   science = { git = "https://github.com/khughitt/science.git", subdirectory = "science" }
   ```
   So a bare `uv run science …` inside a consumer runs **a published revision that contains none of
   this plan** — no `mixin-hypothesis-1.0`, no `entity_extensions`, no new checks. It does not
   error. **It passes, on the old toolkit, and the green is meaningless.** This is the silent
   instrument the whole arc exists to abolish, wearing its most convincing disguise: a real command,
   in the real repo, exiting 0.

   Every consumer-side invocation therefore **names the worktree** and **asserts what it loaded** —
   by **exact path equality**, against a path derived from `$WT` itself:
   ```bash
   WT=$(realpath ~/d/science/.claude/worktrees/instrument-result/science)
   EXPECT="$WT/src/science_tool"

   # ASSERT, don't assume. A typo'd --project silently falls back to the pinned revision.
   uv run --project "$WT" python - <<PY
   import pathlib, sys, science_tool
   got = pathlib.Path(science_tool.__file__).resolve().parent
   want = pathlib.Path("$EXPECT").resolve()
   if got != want:
       sys.exit(f"WRONG TOOLKIT\n  loaded:   {got}\n  expected: {want}")
   print("toolkit OK:", got)
   PY

   uv run --project "$WT" science validate      # ...and every other command
   ```

   > **Substring tests on the path are FAIL-OPEN, and every one I first wrote was.** `'.worktrees'
   > in p.parts` passes for **any other worktree** — including a stale one from a different branch,
   > which is exactly the mix-up worth catching. `'science/src' in str(p)` passes for the **main
   > checkout**, which does not contain this branch either. A check that admits the two nearest
   > wrong answers is not a check. **Compare the resolved path to the one derived from `$WT`, and
   > require equality.**

   > **`--project` may be dropped only after the CONSUMER RE-PINS — not merely after merge.** A
   > consumer's toolkit revision is frozen in **its own `uv.lock`**. Merging to `main`, or even
   > pushing, changes nothing for that consumer until its lock is updated (`uv lock --upgrade-package
   > science`) and the new revision is committed **there**. Until then a bare `uv run` still loads
   > the old revision, and the assertion above is the only thing that will say so.

   If `science_tool` resolves into the **consumer's own `.venv`**, it is the pinned revision, **not
   this branch.** Applies to Task 11 Steps 0/1/3, Task 12 Step 3, and any ad-hoc check.

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
| **2 — Schema substrate (P2)** | 5, 6, **6b**, 7, **7a** | **No** | base 2.0, core mixin, **project extensions**, D3 validator + verdict-evidence graph check — all **wired**, strict, green; **the D4 gate executed, and three of its four legs landed** |
| **3 — The atomic slice (P2m)** | 8–11 | **YES** | all 18 roots migrated, graph-diffed, validate exit 0 |
| **4 — Ratchet (P3)** | 12 | No | `hypothesis` → ERROR |

**Ownership partition (design rev 8) runs through the whole plan.** A field is **core**,
**project-extension**, **renamed/migrated**, or **derived/deleted** — never "declared because we
saw it." Task 2 decides; Task 6 encodes core; **Task 6b composes project extensions**; Task 9
applies renames and deletions. Strictness (`unevaluatedProperties: false`) cannot land before 6b,
because closing the schema without project extensions would force mm30's one-project fields into
the core mixin for all 22 projects.

**A vocabulary is not a capability (design D4).** Declaring `superseded` in a status enum does not
make a kind *supersedable*: the lineage relation must admit it as an endpoint, and the supersession
operation must produce a record that satisfies the schema. **All three, or the terminal is a dead
letter.**

The triangle for `hypothesis` is closed across **two** tasks, and it matters which:

- **Task 7a** *executes* the D4 gate instead of stating it — which is how we learned it fails for
  **twelve** other kinds and not the three the design named — and lands the legs it can while
  Phase 2 is still meaning-neutral: the schema admits the canonical `relations:` edge, the
  `sci:supersedes` relation admits `hypothesis` as an endpoint, and the *operation* is fixed
  generically (exercised on `interpretation`, which is supersedable today).
- **Task 8** lands the **vocabulary** leg — `superseded` in the hypothesis descriptor — and that is
  the act that closes the triangle. Until it lands, `_supports_superseded("hypothesis")` is `False`,
  `mark_superseded` routes every hypothesis to `skipped_kinds`, and the derived gate cannot even
  *see* `hypothesis` (it is absent from the `declares superseded` population). Task 8 is therefore
  also where the hypothesis apply-tests live.

Landing the vocabulary leg **first** would have taken the half-wired count from twelve to thirteen
and failed the gate — which is precisely what the gate is for.

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
    # `profile`, `type`, `aliases`, `content_preview`. Note `profile` and `aliases` are ALSO
    # authored (3 files each) -- `_enrich_raw` only fills them when absent -- which is precisely
    # why the inventory must read the file's own bytes: from the enriched dict, an authored value
    # and an injected one are indistinguishable, and `profile` would look derived. It is not.
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
`identification`, `superseded_by`, `resynthesized_into`.

**Core, but owned by the deferred P1 capability subsystem (3):** `required_capabilities`,
`capability_scope`, `composition_rule` — declared, not absorbed.

**Derived / delete (1):** `phase` (folds into `status`, rev 7).

> ⚠️ **This paragraph is SUPERSEDED by Task 2's adjudication artifact
> (`2026-07-12-hypothesis-field-adjudication.md`) — read that, not this.** It is kept only to show
> what the pre-adjudication list said. Two errors it contained: it called **`profile` derived and
> told the migration to strip it** (Task 2 §3 proved an authored `profile` is *honored* —
> `sources.py:765-772` is **fill-if-missing**, it reaches `sci:profile` at `materialize.py:640`, and
> it drives `registration_state`), and it kept **nine keys in core that Task 2 removed**.
> **Task 6 and Task 6b are generated from the artifact.**

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
2. **Every authored verdict must have a qualifying, resolvable basis at graph time — NOT only when
   `status: complete`.** A verdict with nothing behind it is a fabrication whatever the lifecycle
   says. *(Rev 2 of this plan scoped the graph check to `complete` only. Wrong — and it would have
   let a `draft` hypothesis assert `refuted` with no evidence at all.)*

   **A qualifying basis is exactly two things, and their REACH DIFFERS** (rev 9 — this clause said
   *"evidence **or interpretation** basis"* for three revisions, and **neither half of that was
   implementable as written**):

   - an **admissible, polarity-agreeing evidence-line unit** — on the hypothesis **or a core
     member**. Both reaches are real: the `supports`/`disputes` `RelationKind`s admit a hypothesis
     TARGET from an `evidence-line` SOURCE (`profiles/core.py:648-660`).
   - a **`falsification` record** — on a **core PROPOSITION member, and only there.**
     `FalsificationEntity.falsifies` is required, and `_add_falsification_relations` hard-raises
     unless it resolves to `kind == "proposition"` (`materialize.py:1274`). A falsification *on a
     hypothesis* **cannot exist.**

   **`interpretation` is NOT a basis.** It is not a graph kind at all — no such entity in the
   registry, no typed edge to a hypothesis — so the check cannot read one. Restoring it needs its
   own slice. **A check must never claim a basis it cannot read**, and this contract is the first
   thing an implementer reads, so it says so here rather than only in Task 7.
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
    # Synthetic id. ☠️ Do NOT write the real `0009` into these fixtures with invented values --
    # the author ruled it `complete` + `refuted`, and a fixture that says otherwise is read as
    # migration guidance by the next person. Revs 1-5 of this plan said `retired` + `weakened`
    # here, which is the guess the author overruled (Task 4).
    _hyp(tmp_path, "0042-x", status="retired", phase="candidate")
    inv = inventory(tmp_path)
    assert inv.deterministic == [] and len(inv.ambiguous) == 1
    assert inv.ambiguous[0].target_status is None  # never guessed


def test_an_ADJUDICATION_lets_a_refused_file_through(tmp_path: Path) -> None:
    # THE escape from the refusal loop. Without this, `_classify` sees the terminal status
    # forever and the file can never migrate, no matter what an author does to it.
    #
    # This is the CLOSED-WITHOUT-A-VERDICT shape: the work stopped for non-epistemic reasons, so
    # the verdict stays ABSENT and `closure_basis` carries the reason. Pairing a `closure_basis`
    # WITH a verdict (as revs 1-5 did) is a second, weaker copy of the adjudication -- when the
    # evidence spoke, the verdict IS the reason (Task 4).
    _hyp(tmp_path, "0042-x", status="retired", phase="candidate")
    adj = {
        "hypothesis:0042-x": Adjudicated(
            status="retired", closure_basis="the assay was discontinued; no samples remain"
        )
    }
    inv = inventory(tmp_path, adjudication=adj)
    assert inv.ambiguous == []
    row = inv.deterministic[0]
    assert (row.target_status, row.target_verdict) == ("retired", None)
    assert row.target_closure_basis == "the assay was discontinued; no samples remain"


def test_an_adjudication_can_also_record_that_the_EVIDENCE_SPOKE(tmp_path: Path) -> None:
    # The other shape, and the one `natural-systems/0009` actually is: `complete` + a verdict, and
    # NO `closure_basis`. The decisive test RAN (so the work is concluded, not abandoned) and it
    # rejected the organizing conjecture.
    _hyp(tmp_path, "0009-d", status="retired", phase="candidate")
    adj = {"hypothesis:0009-d": Adjudicated(status="complete", verdict="refuted")}
    row = inventory(tmp_path, adjudication=adj).deterministic[0]
    assert (row.target_status, row.target_verdict, row.target_closure_basis) == (
        "complete",
        "refuted",
        None,
    )


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
> moment Task 7's `verdict.missing-basis` ships, it **fires on the flagship file of this entire arc**
> — the one whose corruption started it. *The adjudication is sound; the graph simply cannot yet
> represent what it rests on.* **A representation obligation, not adjudicative ambiguity.**
>
> **It fires at WARN, and that is exactly why.** An earlier draft of this sentence said it would
> **ERROR**, contradicting this task's own later ruling and Task 7's shipped severity. `0009` is not
> the exception that survives an ERROR rule — it is the *proof the rule cannot be an ERROR yet*:
> **≥11 of the 15 migrating verdicts cannot satisfy it**, so an ERROR would be an uncertified
> instrument failing real builds. That is the original incident, verbatim. `verdict.missing-basis`
> ships **WARN and ungated**, with its **own** ratchet (it stays WARN even after Task 12 certifies
> the *kind* — kind certification is a different axis from rule certification).

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

- [x] **Step 1: Author one evidence-line in `natural-systems`** — **DONE 2026-07-13**, ruled by the
  author, `natural-systems@0ccdeffee`:
  `evidence-line:t585-h09-p3-cycle-lens-bridge-null`. `stance: disputes`, targeting
  `hypothesis:0009-local-structure-globalization-obstruction`, sourced from
  `pipeline/t585/bridge-test-results.json` (the same source `interpretation:0192` cites).
  `strength: strong`, `evidence_role: direct_test`, `dispute_scope: whole_claim`,
  **`independence: shared-source`** (group `t585-h03-t164-instrument`), `evidence_type: simulation`,
  `belief_eligible: true`.

> **The metadata transcribes `0192`; it does not negotiate with the policy.** `simulation` is the
> classification `0192` already authors (*"simulation_evidence (structural, over the frozen
> `hypothesis:0003` cycle complex and the t164 lens matrices)"*, `0192:46`) — computational structural
> evidence over derived artifacts, so no `dataset_usage` and no `evidence.empirical.requires_dataset_usage`
> ERROR. `shared-source` is what `0192`'s own threats section says: *a single instrument; a genuinely
> independent re-derivation was out of scope.*

> **⚠️ The epistemic metadata is an AUTHOR'S judgment — do not invent it.** `evidence_role`,
> `strength`, `independence`, and whether the dispute is **whole-claim/decisive** are exactly the
> knobs that decide whether `is_decisive_refutation` fires. A migration that guessed them would be
> manufacturing the evidence for the verdict it is migrating — the precise fabrication this design
> exists to prevent. **Ask; do not default.**

- [x] **Step 2: Verify the basis resolves — DONE 2026-07-13, through the SHIPPED machinery.**
  `collect_evidence_units(k, p, _evidence_targets_for_uri(k, <0009>))` returns **1 unit**:
  `stance=disputes`, `is_qualifying_direct_test=True`, `is_proxy_gated=False`. So `0009`'s verdict now
  has an **admissible, polarity-agreeing basis** and `verdict.missing-basis` will not fire on it.

> ### The basis is REAL and the computed disagreement is REAL. Both. Do not "fix" the second.
>
> `is_decisive_refutation` returns **`False`** on this unit — and that is the correct, intended
> outcome, not a defect to be tuned away. The rule requires an **`independent`** strong whole-claim
> direct test (`belief.py:258-271`); this instrument is `shared-source`, so the line **contests but
> cannot eliminate**. `verdict.disagrees-with-computed` (WARN, report-only) is therefore *expected* to
> fire on `0009`, and it will be telling the truth about two **compatible** facts:
>
> 1. the author adjudicated `0009` as `refuted` under **its own pre-registered decision rule**; and
> 2. Science's **generic** belief policy cannot *independently* reproduce that adjudication from one
>    shared-source instrument.
>
> **Adjusting `independence` to `independent` would silence the warning by manufacturing the evidence
> for the verdict it is recording** — the exact fabrication this design exists to prevent, and the
> reason the ⚠️ box above says *ask, do not default*. The honest closures are an independent
> re-derivation of the cycle complex, or the heavier path (promote P3 to a proposition + author a
> `falsification`). Neither is Task 3b's.
>
> **This is also the first live demonstration that the two rules are independent instruments** —
> `missing-basis` is satisfied while `disagrees-with-computed` fires. A single "verdict is wrong" rule
> could not have expressed this state, and would have forced a false choice between deleting the
> adjudication and faking the evidence.

**Provenance debt, logged not paid:** `natural-systems`' **model catalog is not a `dataset:` entity**
(all seven of its datasets are external — arXiv, SNAP, SocioPatterns, USGS). That is why an
`empirical_data` classification could not have declared `dataset_usage` honestly. Real gap; **not this
task's**, and not a reason to misclassify the evidentiary modality.
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

### Task 5: `science-entity-base-2.0` — syntactic kind, so it never needs editing again — **DONE** (`c83c964c`)

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

- [x] **Step 1: Write the failing test**

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

- [x] **Step 2: Run and fail** — `SchemaNotFoundError`: the file does not exist.

- [x] **Step 3: Create the schema.** Copy `science-entity-base-1.0.json`, keep `$defs`,
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

- [x] **Step 4: Green — the WHOLE suite**, not a selection. `cd science/model && uv run --frozen
  pytest`, then `cd science && uv run --frozen pytest`. Task 5 adds a schema file and three
  file-shape tests; nothing it commits can be red.

- [x] **Step 5: Commit.**

---

### Task 6: Profile plumbing, `validate_as`, and `mixin-hypothesis-1.0`

**One task, because the mixin's invariants and the machinery that executes them cannot go green
separately** — and **no task may end red.**

**Files:**
- Modify: `science/model/src/science_model/entity_schema/profile.py`, `validator.py`
- Create: `science/model/src/science_model/schemas/mixin-hypothesis-1.0.json`
- **Modify: `science/model/src/science_model/reasoning.py:189` (`RivalModelPacket`)** — the
  single-rival form (Step 3c). It lands **here, not in Task 8**: Step 3b closes the packet `$def`,
  and a closed `$def` with no model fields fails `protein-landscape/0001` for as long as the two are
  apart.
- Test: `science/model/tests/test_project_profiles.py`, `test_mixin_hypothesis.py`
- **Test: `science/tests/test_graph_materialize.py`** — Step 4c, and it is in the **toolkit**
  package, not the model one. That is the whole reason Step 4 below runs *both* suites: a gate that
  lives in a suite the task never runs is not a gate.

**Interfaces:**
- Produces `EntityValidator.validate_as(entity: dict, profile: ProfileString) -> None` — validate
  against an **explicit** profile. Project entities do **not** carry `schema_profile` in
  frontmatter; it is derived from `kind`. Tasks 8–10 call this.
- Produces `default_profile_for_kind("hypothesis")` → `science-entity-base/2.0+hypothesis/1.0`.

- [x] **Step 1: Write the failing tests**

```python
# science/model/tests/test_project_profiles.py
import pytest

from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    default_profile_for_kind,
    parse_profile,
)
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


# An OTHERWISE-VALID external dataset. Every field here is load-bearing, and the first draft of
# this test had none of them: `dataset:x` fails the dataset mixin's own id pattern (min 2 chars),
# `tier: raw` is not in the tier enum, `origin: external` REQUIRES `access`, and a `deposit`
# dataset REQUIRES `datapackage`. That payload failed for five reasons, only one of which was the
# `const` -- so the test passed with the const DELETED. A test that cannot fail certifies nothing.
_VALID_DATASET = {
    "id": "dataset:example-cohort", "kind": "dataset", "title": "T",
    "created": "2026-07-13", "updated": "2026-07-13",
    "origin": "external", "tier": "use-now",
    "datapackage": "data/example-cohort/datapackage.json",
    "access": {"level": "public", "verified": True},
}
_BASE2_DATASET = parse_profile("science-entity-base/2.0+dataset/1.0")


def test_the_dataset_control_payload_is_otherwise_VALID() -> None:
    # THE CONTROL. It is the only thing that gives the next test its meaning: it proves the
    # payload's ONLY defect is the one the next test injects. Without it, the next test is
    # asserting that an invalid record is invalid.
    EntityValidator().validate_as(dict(_VALID_DATASET), _BASE2_DATASET)


def test_a_mixin_const_still_narrows_the_kind_under_base_2() -> None:
    # MOVED HERE FROM TASK 5: it needs `validate_as`, which lands in this task.
    #
    # Base 2.0's `kind` is a PATTERN, so the base alone accepts any lowercase word -- `hypothesis`
    # included. The entire safety argument for widening it is that the mixin re-pins the kind with
    # a `const`. Untested, that argument is a comment. Here it is, executed.
    with pytest.raises(EntityValidationError) as exc:
        EntityValidator().validate_as(dict(_VALID_DATASET, kind="hypothesis"), _BASE2_DATASET)

    # Assert the REASON, not merely the failure. The error set must be exactly {kind}: if any
    # other field also failed, the payload is no longer a control and the const is untested again.
    failed = {
        (err.absolute_path[0] if err.absolute_path else "<root>") for err in exc.value.errors
    }
    assert failed == {"kind"}
```

```python
# science/model/tests/test_mixin_hypothesis.py
import json
from importlib.resources import files

import pytest

from science_model.entity_schema import (
    EntityValidationError, EntityValidator, default_profile_for_kind,
)

PROFILE = default_profile_for_kind("hypothesis")
V = EntityValidator()
MIXIN = json.loads(
    (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
)


def _h(**over) -> dict:
    base = {"id": "hypothesis:0001-x", "kind": "hypothesis", "title": "T",
            "created": "2026-07-12", "updated": "2026-07-12", "status": "active"}
    base.update(over)
    return base


# ---------------------------------------------------------------------------------------------
# TASK 2's ADJUDICATION, AS DATA. The authority is
# `docs/plans/2026-07-12-hypothesis-field-adjudication.md`; this is its executable form, and the
# schema is checked against IT rather than against a hand-kept list in the plan's prose. Regenerate
# AUTHORED_KEYS with `science entity field-inventory --kind hypothesis` across the roster.
# ---------------------------------------------------------------------------------------------

# Task 2 has FOUR dispositions, and rename is not delete. Collapsing them loses the one fact the
# migration needs: a RENAMED key has a TARGET that must exist and must receive its value; a DELETED
# key has none. Both end up `false` in the mixin -- but for opposite reasons, and only one of them
# obliges the migration to write something.

# §2, §3, §4, §6-keep -- an accepted toolkit contract owns the semantics.
CORE = {
    "id", "kind", "title", "status", "created", "updated",       # §2 structural
    "related", "source_refs",                                    # §2 resolution/graph edges
    "origins", "added_by", "lens_views", "ontology_terms",       # §3 real readers
    "datasets", "review_state", "aliases", "profile",
    "composition_rule", "description", "rival_model_packet",
    "required_capabilities", "capability_scope",                 # §4 capability side-channel
}

# NEW core -- 0 authored today; core BEFORE any reader ships (design rev 8/9).
NEW_CORE = {"verdict", "closure_basis", "superseded_by", "resynthesized_into"}

# §5 PROJECT-EXTENSION -- real fields, owned by ONE project. Must be UNDECLARED in core: admission
# is Task 6b's to grant, and `false` here would make the extension unsatisfiable.
PROJECT_EXTENSION = {
    "confidence_label", "confidence_mechanistic_label", "identification",   # mm30
    "external_hypothesis_id",                                              # evolution
}

# §6 RENAME / MIGRATE -- the VALUE survives; only its home changes. The migration MUST write the
# target. `false` on the source key, so the old spelling can never come back.
RENAMED_TO_FIELD = {
    "phase": "status",                                    # design rev 7 -- `phase` IS the lifecycle
    "author_stated_evidence": "source_stated_evidence",   # -> extension-evolution.provenance (§6)
    "promoted_from": "origins",                           # its values are literally source paths
}

# ...and one whose target is not a FIELD at all. `confidence` becomes author-written
# `expert_judgment` evidence-line ENTITIES (§5b). Two scalars do not specify a target proposition,
# stance, source, strength or independence -- so the migration must REFUSE to synthesize them, and
# there is no key here for it to write. Kept distinct from a delete precisely because the value is
# not garbage; it is under-specified, and only the author can finish it.
RENAMED_TO_ENTITY = {"confidence": "evidence-line (expert_judgment) -- AUTHOR-WRITTEN, never migrated"}

# §7 DERIVED / DELETE -- no target. The value does not survive, and nothing is owed to it.
DELETED = {
    "belief_state",          # derived: belief.py's _claims() already covers Hypothesis (Task 2b)
    "evidence_stance",       # §5b: collapses durable origin with time-varying coverage
    "tags",                  # already ruled legacy by the toolkit's OWN health check
    "priority", "role", "domain", "promotion_criteria",   # no owned semantics (§7)
}

RENAMED = set(RENAMED_TO_FIELD) | set(RENAMED_TO_ENTITY)
FORBIDDEN = RENAMED | DELETED      # everything `false` in the mixin, for two different reasons

# Every field a PROJECT EXTENSION declares (Task 6b). Note it is not the same set as
# PROJECT_EXTENSION: `source_stated_evidence` is authored by nobody yet -- it is the rename TARGET
# of `author_stated_evidence`, and it must be declared before the migration can write it.
PROJECT_EXTENSION_TARGETS = PROJECT_EXTENSION | {"source_stated_evidence"}

# The corpus, MEASURED (Task 1) -- written out, NOT computed as the union of the three sets above.
# A derived AUTHORED_KEYS would make the partition test a tautology that passes no matter which
# disposition a key was filed under, or whether the corpus authors it at all. This literal is the
# only thing in the file that the schema is not free to define.
AUTHORED_KEYS = {
    "added_by", "aliases", "author_stated_evidence", "belief_state", "capability_scope",
    "composition_rule", "confidence", "confidence_label", "confidence_mechanistic_label",
    "created", "datasets", "description", "domain", "evidence_stance", "external_hypothesis_id",
    "id", "identification", "kind", "lens_views", "ontology_terms", "origins", "phase",
    "priority", "profile", "promoted_from", "promotion_criteria", "related",
    "required_capabilities", "review_state", "rival_model_packet", "role", "source_refs",
    "status", "tags", "title", "updated",
}
assert len(AUTHORED_KEYS) == 36


_LIST_KEYS = {"related", "source_refs", "origins", "lens_views", "ontology_terms", "datasets",
              "aliases", "tags", "required_capabilities", "resynthesized_into", "same_as"}
_TYPED_KEYS = {
    "created": "2026-07-12", "updated": "2026-07-12",   # `format: date` from base 2.0
    "superseded_by": "hypothesis:0002-y",               # `pattern: ^hypothesis:`
    "verdict": "supported",                             # an ENUM -- "x" is not in it
    # Constrained by THIS task. Every contract added above is a new way for `"x"` to be wrong,
    # so every contract added above owes a sample here. That coupling is the point of the
    # docstring below -- and it is why the four lines went in with the four contracts.
    "composition_rule": "conjunctive",                  # an ENUM
    "capability_scope": "methodological",               # an ENUM
    "review_state": {"last_reviewed": "2026-07-12"},    # an OBJECT, closed
    "rival_model_packet": {"packet_id": "p"},           # an OBJECT, `packet_id` required
}


def _sample(key: str):
    """A SCHEMA-VALID value for each key. The admission tests must fail ONLY on admission.

    Every key with a value constraint needs its own sample. A bare "x" for `created` (a date), for
    `superseded_by` (a pattern) or for `verdict` (an enum) makes an admission test go red for a
    reason that has nothing to do with whether the property is DECLARED -- and it goes red looking
    exactly like a schema defect while actually being a fixture defect. That misdirection is the
    whole cost: the test would be pointing at the wrong file.
    """
    if key in _LIST_KEYS:
        return []
    return _TYPED_KEYS.get(key, "x")


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


def test_no_ADMITTED_field_has_a_VACUOUS_contract() -> None:
    # The structural guard for the whole class of defect. `{}` admits 42; an array with no `items`
    # admits [42]; an object with neither `properties` nor `$ref` admits {"anything": 1}. Each of
    # those LOOKS like a declaration and is the absence of one -- and a reviewer scanning the mixin
    # reads them as "declared". Five core fields shipped that way in the first draft.
    #
    # This does not check that the contract is RIGHT (that is
    # `test_the_schema_is_at_least_as_strict_as_the_projection`, Task 8). It checks that a contract
    # EXISTS -- which is the part a human eye slides straight over.
    def _resolve(spec: dict) -> dict:
        # Follow `$ref` into `$defs` -- otherwise the guard is itself vacuous for every field
        # whose contract is a `$def`, which is five of the six it most needs to check.
        ref = spec.get("$ref")
        if not ref:
            return spec
        assert ref.startswith("#/$defs/"), f"unexpected ref {ref}"
        target = MIXIN["$defs"].get(ref.removeprefix("#/$defs/"))
        assert target, f"{ref} does not resolve"
        return target

    for name, spec in MIXIN["properties"].items():
        if spec is False:
            continue  # forbidden -- an absent contract is the POINT
        assert spec != {}, f"{name}: `{{}}` is not a contract; it admits 42"
        resolved = _resolve(spec)
        if resolved.get("type") == "array":
            item = resolved.get("items")
            assert item, f"{name}: an array with no `items` admits [42]"
            assert _resolve(item) != {}, f"{name}: `items: {{}}` admits [42]"
        if resolved.get("type") == "object":
            assert (
                "properties" in resolved
                or "additionalProperties" in resolved
                or "propertyNames" in resolved
            ), f"{name}: an object with no constrained keys admits anything"


def test_every_authored_key_has_EXACTLY_ONE_disposition() -> None:
    # The 36 keys the corpus actually authors (`science entity field-inventory --kind hypothesis`,
    # Task 1) partition into Task 2's FOUR dispositions -- no key in two, no key in none. A key that
    # falls through the partition is a key the schema has not decided about, and it will be decided
    # by accident at migration time.
    groups = [CORE, PROJECT_EXTENSION, RENAMED, DELETED]
    assert set().union(*groups) == AUTHORED_KEYS
    for i, a in enumerate(groups):
        for b in groups[i + 1:]:
            assert not (a & b), f"{sorted(a & b)} has two dispositions"


def test_every_RENAMED_key_has_a_TARGET_and_the_target_is_ADMITTED_SOMEWHERE() -> None:
    # Rename is not delete, and this is the assertion that makes the difference load-bearing: a
    # renamed key's VALUE must have somewhere to land. `source_stated_evidence` lives in
    # extension-evolution.provenance (Task 6b), so it is legitimately not in the core mixin -- but it
    # must not be nowhere. A rename whose target nobody declared is a delete with better manners.
    for source, target in RENAMED_TO_FIELD.items():
        assert MIXIN["properties"][source] is False, f"{source} must be un-resurrectable"
        assert target in CORE or target in PROJECT_EXTENSION_TARGETS, (
            f"{source} -> {target}: the target is declared nowhere"
        )
    # And the one whose target is an ENTITY, not a field: nothing to write, and the migration must
    # REFUSE rather than synthesize it (§5b). Assert only that the key itself is gone for good.
    for source in RENAMED_TO_ENTITY:
        assert MIXIN["properties"][source] is False


def test_CORE_keys_are_admitted() -> None:
    # Each core key, one at a time -- a single kitchen-sink payload would let one key's rejection
    # hide behind another's.
    for key in CORE - {"id", "kind", "title", "status"}:  # the four are already in _h()
        V.validate_as(_h(**{key: _sample(key)}), PROFILE)


def test_the_NEW_core_fields_are_admitted_AS_A_SET() -> None:
    # `verdict` and `closure_basis` get their own conditional tests below, and that is exactly how
    # `resynthesized_into` and `superseded_by` could quietly vanish from the schema while the suite
    # stayed green. They are core BEFORE any reader ships (rev 8/9); nothing else asserts they exist.
    for key in NEW_CORE:
        assert key in MIXIN["properties"], f"{key} is core and undeclared"
        V.validate_as(_h(**{key: _sample(key)}), PROFILE)


def test_archived_requires_a_basis() -> None:
    # The `archived` half of the terminal contract -- the one with no other test in this file.
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="archived"), PROFILE)
    V.validate_as(_h(status="archived", closure_basis="folded into the h5 reframing"), PROFILE)


def test_PROJECT_EXTENSION_keys_are_ABSENT_FROM_CORE_but_not_FORBIDDEN_BY_IT() -> None:
    # Two assertions, and BOTH matter.
    for key in PROJECT_EXTENSION:
        # (a) core alone rejects it -- else the mixin swallowed a one-project field into the
        #     shared vocabulary of all 22 projects, which is the rev-2 defect.
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(**{key: _sample(key)}), PROFILE)
        # (b) core does NOT declare it `false` -- else Task 6b is UNSATISFIABLE. `allOf` intersects,
        #     so `false` in the mixin ∧ `{type: string}` in mm30's extension is a contradiction: every
        #     mm30 hypothesis would fail, with no hint pointing at the mixin. Admission for these keys
        #     is Task 6b's to grant; the mixin must be SILENT, not hostile.
        assert key not in MIXIN["properties"]


def test_FORBIDDEN_keys_are_rejected_and_UNRESURRECTABLE() -> None:
    for key in FORBIDDEN:
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(**{key: _sample(key)}), PROFILE)
        # `false`, not merely undeclared: a field D5 DELETED must not come back through a project
        # extension. This is the line that makes `tags` (which base 2.0 still declares!) actually
        # illegal -- `unevaluatedProperties` cannot reject what the base declared.
        assert MIXIN["properties"][key] is False


def test_a_field_the_BASE_declares_is_still_rejected_when_the_mixin_says_false() -> None:
    # The trap this test exists for: `unevaluatedProperties: false` does NOT reject base-declared
    # keys -- they ARE evaluated. Without the mixin's explicit `false`, base 2.0 would silently
    # re-admit `tags`, the field the toolkit's own health check exists to remove.
    assert "tags" in json.loads(
        (files("science_model.schemas") / "science-entity-base-2.0.json").read_text(encoding="utf-8")
    )["properties"]
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(tags=["legacy"]), PROFILE)


# ---- the inherited surface: base 2.0's properties, decided EXPLICITLY (see the table above) ----


@pytest.mark.parametrize("key", ["schema_profile", "version", "sources", "licenses", "contributors"])
def test_the_INHERITED_prohibitions_are_structural(key: str) -> None:
    # `unevaluatedProperties: false` cannot reject what the BASE declares -- these five are declared
    # there, so only the mixin's `false` makes them illegal on a hypothesis. Without this test the
    # audit that produced them lives in prose, and prose does not fail a build.
    assert MIXIN["properties"][key] is False
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(**{key: "x"}), PROFILE)


def test_the_INHERITED_admissions_actually_validate() -> None:
    # The other half of the same audit, and the half that is easy to get wrong by omission: `same_as`
    # and `dataset_usage` are live owned semantics for ANY project kind (Entity:317 -> sameAs edges at
    # materialize.py:889; Entity:444 has its own graph module). Zero hypotheses author them today, so
    # forbidding them would have looked free -- and would have deleted a capability.
    V.validate_as(_h(same_as=["hypothesis:0002-y"]), PROFILE)
    V.validate_as(_h(dataset_usage=[{"ref": "dataset:x", "role": "analyzed"}]), PROFILE)
```

> `test_schema_and_descriptor_agree` **belongs to Task 8, and is not in this file.** It reads
> `CORE_PROFILE`'s hypothesis descriptor, which Task 8 rewrites — so here it could only be red or
> xfailed, and *an xfail is a red suite wearing a hat.* It travels with the change it gates; do not
> import `CORE_PROFILE` in Task 6.

- [x] **Step 2: Run and fail.**

- [x] **Step 3: Implement the profile plumbing.** In `profile.py` replace line 16 and lines 75–102:

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

- [x] **Step 3b: Write `mixin-hypothesis-1.0.json` — GENERATED FROM TASK 2'S ARTIFACT, not from this
  plan's prose.** `docs/plans/2026-07-12-hypothesis-field-adjudication.md` is the authority; every
  key below traces to a disposition there. The mixin is **materially smaller** than the pre-Task-2
  draft: nine keys left core (`identification`, `tags`, `priority`, `role`, `promoted_from`,
  `promotion_criteria`, `domain`, `external_hypothesis_id`, `confidence_label` /
  `confidence_mechanistic_label`), and `profile` — which the draft deleted — is **kept**.

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
    "id": { "type": "string", "pattern": "^hypothesis:", "$comment": "PREFIX only — base 2.0 owns the id's shape (it is kind-agnostic by design), and the mixin owns its identity. Without this, base 2.0's generic pattern happily admits `id: dataset:foo` on a hypothesis: the `kind` const would pass and the id would name a different entity. Deliberately NOT a full slug pattern — inventing one would hard-fail whichever of the 147 ids I did not think of." },

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
      "type": "string", "pattern": "\\S",
      "$comment": "`\\S`, NOT `minLength: 1` — a single space has length 1, so `closure_basis: \" \"` discharged `retired` while saying nothing."
    },

    "superseded_by": { "type": "string", "pattern": "^hypothesis:" },
    "resynthesized_into": {
      "type": "array", "minItems": 1, "items": { "type": "string", "pattern": "^hypothesis:" },
      "$comment": "A LIST — see archive.py:38 and materialize.py:155. `minItems: 1` because the terminal conditionals key off PRESENCE: `resynthesized_into: []` is present, so it closed a hypothesis naming no successor."
    },

    "related": { "type": "array", "items": { "type": "string" } },
    "source_refs": { "type": "array", "items": { "type": "string" } },
    "aliases": { "type": "array", "items": { "type": "string" } },
    "datasets": { "type": "array", "items": { "type": "string" } },
    "added_by": { "type": "string" },
    "profile": { "type": "string", "$comment": "AUTHORED and honored — `sources.py:765-772` is fill-if-missing, `materialize.py:640` emits sci:profile, `entities_inventory.py:195-199` derives registration_state from it. 3 files author it. An earlier draft called it derived and stripped it; that was wrong." },

    "origins": { "type": "array", "items": { "$ref": "#/$defs/origin_record" } },
    "lens_views": { "type": "array", "items": { "$ref": "#/$defs/lens_view" } },
    "review_state": { "$ref": "#/$defs/review_state" },
    "rival_model_packet": { "$ref": "#/$defs/rival_model_packet" },
    "composition_rule": { "enum": ["all_steps", "conjunctive"], "$comment": "The IMPLEMENTED rules (`WEAKEST_LINK_COMPOSITION_RULES`), NOT all of `CompositionRule`. `evidence_union` and `faceted_support` are RESERVED — declared so the names are stable, and rejected at load by `Entity._validate_composition_rule` (entities.py:494). Enumerating all four would admit two values the model refuses: an authored `evidence_union` would pass schema validation and then crash the loader, which is the schema pointing at the wrong file." },

    "required_capabilities": { "type": "array", "items": { "$ref": "#/$defs/capability_map" }, "$comment": "38 files, 3 projects. P1 subsystem — DECLARED, not yet absorbed. Reaches its readers through a raw-frontmatter re-parse today; undeclared, strictness hard-fails all 38. NO `minItems`: `[]` is `missing` to `_capability_shape_issue`, which is a WARN — the schema must not promote it to a hard failure." },
    "capability_scope": { "enum": ["reference-substrate", "derived-product", "methodological", "model-system", "clinical-outcome", "epidemiological", "behavioral-instrument"] },

    "phase": false,
    "disposition": false,
    "disposition_basis": false,
    "belief_state": false,
    "evidence_stance": false,
    "author_stated_evidence": false,
    "tags": false,
    "priority": false,
    "role": false,
    "domain": false,
    "promoted_from": false,
    "promotion_criteria": false,
    "confidence": false,

    "schema_profile": false,
    "version": false,
    "sources": false,
    "licenses": false,
    "contributors": false
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
      "then": { "required": ["closure_basis"] }
    }
  ],

  "$defs": {
    "origin_record": {
      "$comment": "`OriginRecord` (entities.py:241) — `extra=forbid`, so `additionalProperties: false` is the FAITHFUL translation, not added strictness.",
      "type": "object",
      "additionalProperties": false,
      "required": ["type"],
      "properties": {
        "type": { "enum": ["user", "assistant", "literature"] },
        "ref": { "type": "string" },
        "date": { "type": "string", "format": "date", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$" },
        "independent": { "type": "boolean" },
        "note": { "type": "string" }
      },
      "allOf": [
        {
          "$comment": "`OriginRecord._validate`: a literature origin without a resolvable ref is an unfalsifiable provenance claim. The schema CAN express this one, so it does — and Pydantic must not also.",
          "if": { "properties": { "type": { "const": "literature" } }, "required": ["type"] },
          "then": { "required": ["ref"], "properties": { "ref": { "pattern": "^(paper|cite):" } } }
        }
      ]
    },
    "lens_view": {
      "$comment": "`LensView` (entities.py:273) — `extra=forbid`. The `lens` enum MIRRORS `science_model.lenses.LENS_SLUGS`; `test_the_lens_vocabulary_is_not_a_SECOND_authority` fails the moment a lens is added without regenerating it.",
      "type": "object",
      "additionalProperties": false,
      "required": ["lens", "rationale"],
      "properties": {
        "lens": { "enum": ["analogy", "contrarian", "mechanism", "methodology", "population", "temporal"] },
        "rationale": { "type": "string", "pattern": "\\S" },
        "origin_ref": { "type": "string" }
      }
    },
    "review_state": {
      "$comment": "`EpistemicReviewState` (entities.py:138). `review_horizon_days` must be POSITIVE. `additionalProperties: false` is STRICTER than the model (`extra=ignore`) — deliberately: a typo'd key inside `review_state` is silently dropped today, which is the exact class of defect this arc exists to end.",
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "last_reviewed": { "type": "string", "format": "date" },
        "last_review_note": { "type": "string" },
        "review_horizon_days": { "type": "integer", "exclusiveMinimum": 0 }
      }
    },
    "rival_model_packet": {
      "$comment": "`RivalModelPacket` (reasoning.py:189) — CLOSED, and extended with the SINGLE-RIVAL form the corpus actually authors. Step 3c of THIS task adds the same four fields to the model, with `exclude_if` so existing packets do not churn. Schema and model move together, in one commit, or `protein-landscape/0001` fails validation in the gap.",
      "type": "object",
      "additionalProperties": false,
      "required": ["packet_id"],
      "properties": {
        "packet_id": { "type": "string", "pattern": "\\S" },   // NOT minLength: 1 -- a space has length 1
        "target_hypothesis": { "type": "string" },
        "target_inquiry": { "type": "string" },
        "current_working_model": { "type": "string" },
        "alternative_models": { "type": "array", "items": { "type": "string" }, "$comment": "The LIST form. Authored by ZERO files." },
        "rival_id": { "type": "string" },
        "rival_name": { "type": "string" },
        "rival_claim": { "type": "string" },
        "discriminator_status": { "type": "string" },
        "shared_observables": { "type": "array", "items": { "type": "string" } },
        "discriminating_predictions": { "type": "array", "items": { "type": "string" } },
        "adjudication_rule": { "type": "string" }
      }
    },
    "capability_map": {
      "$comment": "`_capability_shape_issue` (validate/checks/dataset_capabilities.py:197): a non-empty mapping of non-empty string keys to non-empty string values.",
      "type": "object",
      "minProperties": 1,
      "propertyNames": { "pattern": "\\S" },
      "additionalProperties": { "type": "string", "pattern": "\\S" }
    }
  }
}
```

> ### PRESENCE is not a BASIS — the four terminal conditionals fail open unless the VALUE is constrained
>
> The terminal rules are `required`, and **`required` is satisfied by an empty value.** The first
> shipped mixin therefore accepted every one of these:
>
> | payload | why it passed | what it means |
> |---|---|---|
> | `superseded` + `resynthesized_into: []` | the key is present | closed, naming **no successor** |
> | `archived` + `archive_ref: ""` | `{"type": "string"}` admits `""` | closed, pointing **nowhere** |
> | `retired` + `closure_basis: " "` | **`minLength: 1` — a space has length 1** | closed, **saying nothing** |
>
> Each closes a hypothesis while naming nothing, and **the second-order damage is the part that
> matters**: Task 7's cross-record resolver then finds **no reference to dangle**, and reports
> nothing. *The hole survives inside the check built to close it, wearing that check's green as
> evidence.* `minItems: 1` and `pattern: "\S"` are what make the basis a basis — and the six
> payloads are parametrized as regressions, **with controls**, so a later relaxation cannot pass.

> ### `archive_ref` is DELETED — a field whose referent nobody can name is not a basis
>
> Asked what a valid `archive_ref` would even point *at*, the codebase has no answer. It appears in
> **zero source files**, is authored by **zero corpus files**, and — decisively — **has no resolvable
> namespace**: `archive.py` keys its index by the archived entity's **own id**
> (`ArchiveIndex.active_by_id`) and mints no record identifier, so there is nothing on the other end
> of the reference. Path-like (`archive/2026/h1.md`) and `arc:*` spellings both appeared in earlier
> drafts of this plan; **neither resolves to anything**, which is exactly why Task 7 could not have
> built `known_archive_refs` faithfully.
>
> An archived entity's archive record is **already reachable from its `id` alone**. An authored
> pointer to it would be a *second, unversioned spelling of a derivable fact* — the precise collapse
> (`status` vs `phase`) this whole arc exists to undo. **I invented this field in the plan and never
> certified it against the archive layer.** It fails that certification, so `archived` now requires
> `closure_basis`, exactly like `retired`. `NEW_CORE` drops to four, and **Task 7 no longer
> constructs `known_archive_refs` at all.**

> ### The schema is authoritative for SHAPE — so it must actually *have* one
>
> The first draft of this mixin declared `"review_state": {}`, `"composition_rule": {}`,
> `"rival_model_packet": {}`, `"origins": {"type": "array"}` and `"datasets": {"type": "array"}`.
> **An empty schema admits `42`. An array with no `items` admits `[42]`.** Every one of those five
> payloads passes that mixin and is *rejected by Pydantic* — which stands the design's own rule
> (*"JSON Schema is authoritative for shape and invariants; Pydantic is a projection"*) exactly on
> its head: the **projection** was the only thing enforcing the shape. A property declared `{}` is
> not a contract; **it is the absence of one, spelled in a way that looks like presence** — which is
> worse than leaving it undeclared, because `unevaluatedProperties: false` would at least have
> rejected the key outright.
>
> Two of these are STRICTER than the model, and deliberately: `review_state` and
> `rival_model_packet` are `extra="ignore"` in Pydantic, so an unknown nested key is **silently
> dropped** today. The schema forbids it. Strictness beyond the projection is always allowed —
> what is never allowed is the reverse, and that is what `test_the_schema_is_at_least_as_strict_as_the_projection`
> (Task 8) now executes field-by-field.
>
> `capability_scope` and `lens` become **enums** here, mirroring vocabularies that live in Python
> (`VALID_SCOPES`, `LENS_SLUGS`). That is a duplication, and it is the same bargain already struck
> for `status` ↔ `EntityKind.statuses`: **duplicate the vocabulary, then reconcile it in a test that
> fails on drift.** The alternative — leaving them as bare strings — reintroduces the exact defect
> above, since Pydantic *does* police both.

> ### These contracts were CERTIFIED against the corpus before being written down
>
> A new contract is a **claim about existing files**, and the estimator doctrine applies to it
> exactly as it applied to Task 1's instrument: *certify before depending.* Every contract above was
> run against **every hypothesis file on disk** — a deliberate **superset** of the certified roster
> (**165 files / 22 roots**, vs. the roster's 147/18), because for this question over-inclusion can
> only produce false alarms, never false confidence: *if the superset passes, the roster passes.*
>
> **Result: one violation, and it forced an ADJUDICATION.** `protein-landscape/0001` authors a
> `rival_model_packet` with four keys `RivalModelPacket` does not declare — `rival_id`, `rival_name`,
> `rival_claim`, `discriminator_status` — a *single structured rival* where the model declares a
> *list of strings* (`alternative_models`). Because the model is `extra="ignore"`, **those four
> authored keys are silently dropped at `model_validate` and never reach the graph.**
>
> A first pass "solved" this by leaving the object **open** — which *preserves the defect it
> found*. The file would validate, Pydantic would accept the object, and `model_dump()` would still
> lose all four keys. **"The model accepted it" is not the property that matters; "the value
> survived" is** — and no test in this plan was checking the second one. `protein-landscape` is
> **inside the 147-file roster**, so this is not somebody else's problem deferred; it is a file this
> migration will rewrite.
>
> **Ruled: declare the single-rival form, in BOTH authorities** (schema here, model in Task 8), and
> **close the object**. The corpus decides which spelling is real, and the count is not close:
>
> | form | declared by the model | authored in the corpus |
> |---|---|---|
> | `alternative_models: list[str]` | yes | **0 files** |
> | `rival_id` / `rival_name` / `rival_claim` / `discriminator_status` | **no** | 1 file (every packet there is) |
>
> **The model declares a form nobody writes and drops the form the only author uses.** Declaring it
> preserves the file byte-for-byte, ends the drop, keeps the schema authoritative (closed), and
> blocks nothing. `alternative_models` stays — it is not this plan's business to delete a field on a
> model shared with other kinds — but *"a packet now has two spellings of a rival"* is a real design
> question, and it is filed as one rather than answered by a migration.
>
> The other closures survive because the corpus *earned* them: `origins` (34 files), `lens_views`
> (28), `review_state` (7), `required_capabilities` (38), `capability_scope` (1), `composition_rule`
> (1) — **zero violations**. And `origins`/`lens_views` are `extra="forbid"` in Pydantic anyway, so
> closing them is a faithful translation rather than added strictness.
>
> Two facts fell out of the sweep for free, and both corroborate Task 2: `superseded_by`,
> `superseded_by` and `resynthesized_into` are authored by **0 files** (`NEW_CORE` is genuinely new),
> and **165/165 ids already match `^hypothesis:`** — so the mixin's new id pin costs nothing.
>
> **The `rival_model_packet` silent drop is a real defect and is filed as one** (see *Deferred*, end
> of plan). It is not fixed here, and it is not fixed *by* here.

> ### `false` vs. UNDECLARED — the distinction the whole mixin turns on
>
> `"x": false` is the JSON Schema idiom for *"this property must not appear."* Inside an `allOf` it
> is **absolute: no extension can ever re-admit it**, because `allOf` intersects and a `false` branch
> can never be satisfied. Undeclared is different — `unevaluatedProperties: false` rejects the key
> **unless a composed extension declares it.**
>
> So the two lists are not interchangeable, and mixing them up breaks the design in both directions:
>
> | disposition | mechanism | why |
> |---|---|---|
> | **renamed / migrated** (`phase`→`status`, `author_stated_evidence`→`source_stated_evidence`, `promoted_from`→`origins`, `confidence`→evidence-lines) | **`false`** on the **source** key | The value survives; the **old spelling must not.** `false` makes the migration's own leftovers fail loudly instead of quietly validating. **A rename obliges the migration to write the target** — and the target must be declared *somewhere* (core, or a project extension). *A rename whose target nobody declared is a delete with better manners.* |
> | **deleted** (`belief_state`, `evidence_stance`, `tags`, `priority`, `role`, `domain`, `promotion_criteria`) | **`false`** | No target, nothing owed. And it must **not be resurrectable through a project extension** — `false` is the only spelling that says so. |
> | **project-extension** (`confidence_label`, `confidence_mechanistic_label`, `identification`, `external_hypothesis_id`) | **undeclared** | ⚠️ **Marking these `false` would make Task 6b unsatisfiable** — mm30's extension declares `identification`, and `false ∧ {type: string}` is a contradiction, so *every mm30 hypothesis would fail with no hint why.* They must be **absent from core**, not forbidden by it. |
>
> **`author_stated_evidence` is a RENAME, not an extension of the old key** (ruled 2026-07-13; Task 2
> §6 said so and a first pass at Task 6 quietly re-classified it). `author_stated_evidence` →
> **`source_stated_evidence`**, declared in `extension-evolution.provenance`, **string preserved
> byte-for-byte.** No provenance is fabricated; only its **ownership** is made explicit — and the new
> name says what the field is (a *source's* stated evidence) rather than what the old one implied (an
> *author's* epistemic claim, which is exactly the magnitude Task 2b deleted the code for).
>
> **The base's declared fields need an explicit decision too**, because `unevaluatedProperties`
> **cannot** reject what the base already declares. Silence here is not neutrality — it is admission:
>
> | inherited from base 2.0 | decision | why |
> |---|---|---|
> | `tags` | **`false`** | Task 2 §7: **already ruled legacy by the toolkit** — `lingering_tags.py` is a health check whose entire job is to tell you to delete it. Without this line the base **silently re-admits** the field D5 is finishing off. |
> | `sources`, `licenses`, `contributors` | **`false`** | **Not on the project `Entity` model at all** — commons-only. They are silently dropped today. Declaring them would invent a contract; `source_refs` (128 files) and `added_by` (31) are the project spellings, and two spellings of one fact on one kind is the collapse this arc exists to undo. |
> | `same_as`, `dataset_usage` | **admitted** | Real owned semantics for *any* project kind — `Entity:317` → `materialize.py:889` emits sameAs edges; `Entity:444` has its own graph module. Zero hypotheses author them today, but forbidding them would **delete a live capability**, which is not a schema's decision to make. |
> | `description`, `ontology_terms`, `status` | **admitted** | Core (Task 2 §3/§6). The mixin *narrows* `status` from the base's free string to the ruled enum — `allOf` intersects, so narrowing is exactly what it can do. |
> | `schema_profile`, `version` | **`false`** | Derived / commons-only. See Task 5 — the base cannot forbid them (commons authors both), so the mixin must. |

- [x] **Step 3c: The single-rival form on `RivalModelPacket`** (`reasoning.py:189`) — **in THIS task,
  because Step 3b's `$def` closed the object in this task.**

```python
    rival_id: str | None = Field(default=None, exclude_if=lambda v: v is None)
    rival_name: str | None = Field(default=None, exclude_if=lambda v: v is None)
    rival_claim: str | None = Field(default=None, exclude_if=lambda v: v is None)
    discriminator_status: str | None = Field(default=None, exclude_if=lambda v: v is None)
```

> **Why it cannot wait for Task 8.** Step 3 ships `validate_as` and the hypothesis profile, so from
> the moment this task lands, *the mismatch is observable*: a closed `$def` with no model fields
> means `protein-landscape/0001` **fails validation** for two tasks — the schema forbids the four
> keys and nothing declares them. "Schema and model move together" is not a slogan about tidiness;
> **it names the window in which the corpus is broken, and the window has to be zero.**

> ### `exclude_if` is not a style choice — a plain `| None = None` churns the graph
>
> `_model_to_json` (`materialize.py:1897`) is `json.dumps(value.model_dump(mode="json"))` —
> **inclusive**. Four plain optional fields therefore add `"rival_id": null` ×4 to the serialized
> literal of **every** packet, not just protein-landscape's. There are **2 packets** in the corpus
> (1 hypothesis in `protein-landscape`, **1 proposition** in `multiple-myeloma`), so a
> hypothesis-lifecycle migration would silently rewrite `sci:rivalModelPacket` on a **proposition**
> it has no business touching — landing inside the very before/after graph diff Task 11 uses to
> detect exactly that.
>
> `exclude_if=lambda v: v is None` on **the four new fields only** makes the existing literals
> **byte-identical** (verified). The obvious alternative, `model_dump(exclude_none=True)` in
> `_model_to_json`, is *worse*: today's literals already serialize `"target_hypothesis": null` and
> friends, so it would rewrite **both** packets. The narrow fix is the only zero-churn one.

- [x] **Step 3d: The survival test** (`science/model/tests/test_mixin_hypothesis.py`):

```python
def test_the_single_rival_packet_SURVIVES_the_projection() -> None:
    # The whole point of Step 3c, and the property `extra="ignore"` silently violated: the model
    # ACCEPTED this packet all along and `model_dump()` dropped all four keys. Acceptance was never
    # the property worth asserting.
    from science_model.entities import HypothesisEntity

    packet = {"packet_id": "platonic-vs-multimanifold", "rival_id": "platonic-representation-hypothesis",
              "rival_name": "PRH", "rival_claim": "representations converge",
              "discriminator_status": "pre-registered via question:0018"}

    V.validate_as(_h(rival_model_packet=packet), PROFILE)          # the SCHEMA admits it...

    dumped = HypothesisEntity.model_validate(
        {"project": "p", "file_path": "h.md", "content_preview": "", "ontology_terms": [],
         "related": [], "source_refs": [], **_h(rival_model_packet=packet)}
    ).model_dump(mode="json")["rival_model_packet"]

    for key, value in packet.items():                              # ...and the MODEL keeps it.
        assert dumped[key] == value, f"{key} validated and then evaporated"


def test_a_LIST_form_packet_serializes_BYTE_IDENTICALLY() -> None:
    # The collateral-churn guard. `_model_to_json` is an inclusive `model_dump`, so four plain
    # optionals would add four `null` keys to the serialized literal of every EXISTING packet --
    # two of which are on PROPOSITIONS, entities this migration must not touch at all.
    import json

    from science_model.reasoning import RivalModelPacket

    packet = RivalModelPacket(packet_id="p", alternative_models=["m"], shared_observables=["o"])
    serialized = json.dumps(packet.model_dump(mode="json"))

    assert "rival_id" not in serialized
    assert "discriminator_status" not in serialized
```

- [x] **Step 4: Green — BOTH suites, whole, plus lint and types.** Task 6 changes
  `science_model.reasoning`, and Step 4c's guard lives in the **toolkit** package — so a run of only
  the model suite never executes the very test that proves the packet reaches the graph.

```bash
cd science/model && uv run --frozen pytest      # the model suite, whole
cd science       && uv run --frozen pytest      # the TOOLKIT suite -- this is where Step 4c runs
cd science       && uv run ruff check && uv run pyright
```

- [x] **Step 4b: Prove it in the ARTIFACT, not only the unit test.** The corpus holds **exactly 2
  packets, in 2 projects** — `protein-landscape` (1 hypothesis) and `multiple-myeloma` (1
  **proposition**). *(An earlier count of 3 was wrong: `~/d/r/mm30` is a **symlink** to
  `cancer/cancer-types/multiple-myeloma`, so a path-glob counts its proposition twice. Dedupe by
  `Path.resolve()` — this is the duplicate-root trap that also makes `science/meta` and `health/meta`
  collide on `basename`.)*
>
> **Only `multiple-myeloma` is buildable, so only it is gated here.** `protein-landscape`'s
> `graph build` is red today (box below), and the loop this step used to carry ran *both* roots, then
> `cp`'d `knowledge/graph.trig` whether or not the build succeeded — so a failed build would have
> snapshotted the **stale committed graph** and diffed it against itself. That is the silent success
> this task exists to forbid, reintroduced in the step meant to prove its absence. It also left `$N`
> holding the last root, so the `diff` it printed only ever compared one project anyway.
>
> The split of claims:
> - **multiple-myeloma** — buildable, so it carries the real artifact half: **byte-identical**.
> - **protein-landscape's four-key emission** — carried by **Step 4c**, hermetically, at
>   `_model_to_json`, the exact function that writes `sci:rivalModelPacket`.
> - **protein-landscape's real artifact diff** — **deferred to Task 11**, after the alias defect is
>   fixed. It is that task's prerequisite already; it does not become achievable by being asserted
>   harder here.

> ### `uv run science` inside a consumer runs the MAIN checkout, **not this worktree**
>
> Every Science project depends on the toolkit through a *relative editable source*
> (`science = { path = "../science/science", editable = true }`), which resolves to
> **`~/d/science/science`** — the main checkout. Verified: from `~/d/protein-landscape`, plain
> `uv run` imports `science_tool` from `/mnt/ssd/Dropbox/science/science/src/`.
>
> **So a naive `uv run science graph build` would build the "after" graph with Task 6 absent**, show
> no diff, and report zero churn — from an instrument that never ran the change. *That is a
> fabricated verification*, and it is the exact failure this whole arc exists to end: an instrument
> reporting on a thing it cannot see. Point `uv` at the worktree explicitly:

```bash
set -euo pipefail        # NOT optional: it is the only thing that stops a failed build from being
                         # followed by a `cp` of the stale committed graph.

WT=$(realpath ~/d/science/.claude/worktrees/instrument-result/science)   # Global constraint 0:
                                                                        # assert the import path too
SNAP=/tmp/claude-1000
P=~/d/cancer/cancer-types/multiple-myeloma      # the one buildable packet-bearing root

snapshot() {   # $1 = destination. Build in place, copy out, restore -- leave the repo as found.
  cd "$P"
  git status --short knowledge/    # MUST be clean, or the "before" is already somebody else's diff
  uv run --project "$WT" science graph build --local-only   # a failure ABORTS here, not silently
  cp knowledge/graph.trig "$1"
  git checkout -- knowledge/graph.trig
}

snapshot "$SNAP/before-mm.trig"     # BEFORE editing anything (already captured)
# ...apply Task 6...
snapshot "$SNAP/after-mm.trig"

diff "$SNAP/before-mm.trig" "$SNAP/after-mm.trig"    # required: EMPTY
```

  The required outcome: multiple-myeloma's proposition literal is **byte-identical** — no `null`
  keys, no reordering. A hypothesis-lifecycle migration that rewrote a **proposition's** provenance
  would be doing something nobody asked for, inside the diff nobody was reading for it. Diff the
  whole file, not a `grep` of the packet line: the `null`-key churn `exclude_if` exists to prevent
  would land on *every* serialized packet, and a grep narrowed to the field you expect to change is
  blind to exactly the collateral you are looking for.

  The **four-key appearance** is proven by Step 4c, not here — see the box below for why it cannot
  be proven in protein-landscape's artifact yet, and why asserting it anyway would produce a green
  that means nothing.

> ### ⚠️ `protein-landscape`'s graph build is RED **today**, and that blocks Task 11 too
>
> `science graph build` fails there — `Cannot materialize graph with unresolved references:
> question:0004-mega-cluster-split aliases -> q04` — and it fails identically on the **main
> checkout**, so it is pre-existing and not caused by this arc. Two consequences, and the second is
> the one that matters:
>
> 1. **So protein-landscape is OUT of Step 4b entirely** — not "attempted, and skipped if it fails".
>    A build that cannot run has no "after" graph, and `cp`-ing the committed one produces a diff
>    that is empty *because nothing was measured*, which reads identically to a diff that is empty
>    because nothing changed. The packet claim is carried instead by the hermetic materialization
>    test below (a fixture entity, no project), and `multiple-myeloma` — which builds clean — carries
>    the byte-identical half.
> 2. **`protein-landscape` is one of the 18 roots in Task 11**, and Task 11 gates every root on a
>    before/after `graph.trig` diff. **A root whose graph cannot build cannot be gated.** So this is
>    a Task 11 **prerequisite**, not a footnote: either the alias is fixed first, or the root is
>    consciously excluded and the roster re-certified at 17 — *and a silently skipped diff is the one
>    outcome not available*, because it looks exactly like a clean one.

- [x] **Step 4c: The hermetic materialization test** — it does not depend on any project, so it
  still runs while protein-landscape's graph is red (`science/tests/test_graph_materialize.py`):

```python
def test_the_single_rival_packet_REACHES_the_graph() -> None:
    # `_model_to_json` (materialize.py:1897) is what carries the packet into `sci:rivalModelPacket`.
    # The four keys are absent from protein-landscape's graph TODAY -- 0 occurrences -- because the
    # model dropped them before serialization ever saw them.
    import json

    from science_model.reasoning import RivalModelPacket
    from science_tool.graph.materialize import _model_to_json

    packet = RivalModelPacket(packet_id="p", rival_id="platonic", rival_name="PRH",
                              rival_claim="representations converge",
                              discriminator_status="pre-registered")

    emitted = json.loads(_model_to_json(packet))

    assert emitted["rival_id"] == "platonic"
    assert emitted["discriminator_status"] == "pre-registered"


def test_a_LIST_form_packet_emits_NO_new_keys() -> None:
    # The collateral-churn guard, at the layer that writes the artifact. Two packets exist in the
    # corpus and ONE of them is on a proposition -- an entity this migration must not touch.
    import json

    from science_model.reasoning import RivalModelPacket
    from science_tool.graph.materialize import _model_to_json

    emitted = json.loads(_model_to_json(RivalModelPacket(packet_id="p", alternative_models=["m"])))

    assert "rival_id" not in emitted
    assert "discriminator_status" not in emitted
```

- [x] **Step 5: Commit.**

---

### Task 6b: Project extensions — compose them BEFORE closing the schema — **DONE 2026-07-13**

**Without this, `unevaluatedProperties: false` rejects mm30's `confidence_mechanistic_label` — so
the only way to keep mm30 validating would be to promote a one-project field into the core mixin
for all 22 projects.** That is design §6's ownership contract, violated. **Strictness and
project-local fields must arrive together, or strictness cannot arrive at all.**

> ### TWO extensions, not one. `external_hypothesis_id` cannot leave core and have no owner.
>
> Task 2 removed it from core (13 files, **zero readers**, an `EH-###` key belonging to an external
> system). Removal alone would **delete 13 authored identifiers** the moment the schema closes — a
> field cannot be evicted from core *and* left homeless. Same for `author_stated_evidence` (13 files),
> which §5b preserved **as source provenance**.
>
> | extension | project | fields |
> |---|---|---|
> | `extension-mm30.assessment/1.0` | multiple-myeloma | `confidence_label`, `confidence_mechanistic_label`, `identification` |
> | **`extension-evolution.provenance/1.0`** | cancer/mechanisms/evolution | `external_hypothesis_id`, **`source_stated_evidence`** |
>
> `source_stated_evidence` is the **rename target** of `author_stated_evidence` (13 files), ruled
> 2026-07-13: **the string is preserved byte-for-byte**, the old key becomes `false`, and only the
> field's *ownership* changes. Both evolution fields are **opaque authored provenance with zero
> epistemic force** — which is now *structurally* true, not merely asserted, since Task 2b deleted
> the `_authored_magnitude` chain that gave `author_stated_evidence` a belief magnitude.
>
> §6's other option — folding the free text into structured `origins` — needs an `OriginType` and a
> source **per file**, which is **authoring work, not a migration step.** *Do not let the migration
> synthesize it.* The rename **preserves 13 authored values while inventing nothing.**

> **Full 147-file validation does NOT belong in Task 6.** It cannot even run here: the corpus still
> carries `phase`, and mm30/evolution fields have no extension until this task composes them. The
> real gate is the **two-phase preflight in Task 11**, after Task 6b's extensions exist and Task 9
> renders the migrated frontmatter. Task 6 proves the *contract*; Task 11 proves the *corpus*.
> Asserting corpus-wide validity any earlier would be certifying against files that do not exist yet.

Design §6 already names the mechanism: an **additive-only extension component** in the profile,
which may *add* fields to a core kind but never redefine a core one.

> ### ⚠️ The filename is `extension-<name>-<ver>.json` — HYPHENS, and the dots are FLATTENED
>
> `loader.filename_for` has always done `component.name.replace(".", "-")`, which is why all 13
> packaged extensions are `extension-bio-rnaseq-1.0.json` and not `extension-bio.rnaseq-…`. So the
> component `mm30.assessment/1.0` resolves to the file **`extension-mm30-assessment-1.0.json`**.
> A dotted filename is never found, and the failure is a `SchemaNotFoundError` at first use.

**Files:**
- Modify: `science/model/src/science_model/entity_schema/loader.py` — `SchemaLoader(project_dir)`, searching the project dir for **extensions only** (below), and `filename_for` made public
- **Create: `science/model/src/science_model/entity_schema/resolve.py`** — `resolve_profile` + the root contract. **Not `profile.py`:** `resolve_profile` needs `SchemaLoader`, and `loader` already imports `profile`, so putting it there makes the package **cyclic**. `resolve` is the genuine third layer — *profile parses, loader fetches, resolve composes*.
- Modify: `science/src/science_tool/project_config.py` — `entity_extensions` as a **declared** field (`ProjectConfig` is `extra="allow"`, so an undeclared stanza would be accepted, ignored, and silently do nothing — the very failure this arc exists to close)
- **Create: `science/src/science_tool/entity_profiles.py`** — `load_project_schema`, which hands out the profile and the loader **together** (they are only correct together) and **eagerly certifies every declaration**
- Create: `~/d/cancer/cancer-types/multiple-myeloma/schemas/extension-mm30-assessment-1.0.json` *(in mm30, not the toolkit)*
- **Create: `~/d/cancer/mechanisms/evolution/schemas/extension-evolution-provenance-1.0.json`** *(in evolution, not the toolkit)*
- Test: `science/model/tests/test_project_extensions.py`, `science/tests/test_entity_profiles.py`

**Both project repos need a `science.yaml` stanza** — the extension file alone does nothing:

```yaml
# ~/d/cancer/cancer-types/multiple-myeloma/science.yaml
entity_extensions:
  hypothesis: ["mm30.assessment/1.0"]   # -> schemas/extension-mm30-assessment-1.0.json
```

```yaml
# ~/d/cancer/mechanisms/evolution/science.yaml
entity_extensions:
  hypothesis: ["evolution.provenance/1.0"]   # -> schemas/extension-evolution-provenance-1.0.json
```

```json
// ~/d/cancer/mechanisms/evolution/schemas/extension-evolution-provenance-1.0.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-evolution-provenance-1.0.json",
  "title": "evolution: authored source provenance (no epistemic force)",
  "type": "object",
  "properties": {
    "external_hypothesis_id": {
      "type": "string", "pattern": "^EH-[0-9]+$",
      "$comment": "13 files. An external system's key. Zero toolkit readers — declared so the field survives strictness, not because anything acts on it."
    },
    "source_stated_evidence": {
      "type": "string", "pattern": "\\S",
      "$comment": "The RENAME TARGET of `author_stated_evidence` (13 files), preserved byte-for-byte. `\\S`, NOT `minLength: 1` — a single space has length 1, which is the exact defect Task 6 was already corrected for. PROVENANCE ONLY: what the SOURCE said about its own evidence. It is not a magnitude, not a coverage claim, and not an input to belief — Task 2b deleted the `_authored_magnitude` chain that once made it one, so this is now structurally true and not merely documented."
    }
  }
}
```

> ### The PROJECT-EXTENSION ROOT CONTRACT — an ALLOW-list, because a deny-list has a hole
>
> *"Additive only" is not enforced by checking `properties` against core.* A root-level applicator
> narrows the **composed** record from inside its own `allOf` branch **without ever naming a core
> property**, so a `properties`-clean extension can still do all of this:
>
> | root key | what it does to the composed record |
> |---|---|
> | `required: ["verdict"]` | makes a **core** field mandatory for this one project |
> | `not` / `if`-`then` | forbids composed records the core **admits** |
> | `additionalProperties` | inside an `allOf` it **cannot see sibling branches**, so it rejects every field the base and the mixin declare — the exact reason the validator composes with `unevaluatedProperties` instead |
> | `$ref` | pulls in arbitrary constraints from anywhere |
> | `dependentRequired` | conditions a core field on a project field |
>
> **These are not hypothetical.** `extension-bio-geneset-member-1.0.json` **already uses root `not`
> AND root `additionalProperties`.** That is legal for a *commons* extension — authored in this repo,
> reviewed beside the mixin it extends. It is **not** legal for a *project* extension, authored in a
> repo the toolkit never sees.
>
> So the contract is stated **positively**. A project extension may declare `properties`, mark its
> **own** properties `required`, and carry `$schema`/`$id`/`$comment`/`$defs`/`title`/`description`/
> `type: object`. **Nothing else.** Enumerating what is *forbidden* would leave a hole for every
> keyword JSON Schema adds after today — the same *"a scope that is LISTED has a hole by
> construction"* lesson the import guard taught. Enforced by `_certify_root_contract`, plus:
> **`required ⊆ owned`**, **no collision with base or mixin properties**, and **no two extensions
> owning one field** (their constraints would silently intersect and neither owner could see the
> other).

> ### A project's schema dir is searched for EXTENSIONS ONLY — never a base, never a mixin
>
> "Search `project_dir` first, then fall back to package resources" — taken literally — lets a
> project drop its own `mixin-hypothesis-1.0.json` into `schemas/` and **silently redefine the core
> kind for itself**, re-opening, *through the mechanism built to close it*, the per-project
> divergence this whole arc exists to end. **A project may OWN fields; it may not REDEFINE the
> kind.** `SchemaLoader._load` consults `project_dir` only when `is_extension(component)`.
>
> And there is **no fallback to a packaged extension** either: `bio.rnaseq` *is* a packaged
> extension, so a silent fallback would let a project whose own file is missing or misnamed quietly
> validate against a **toolkit** schema of the same name — a field it does not own, under a contract
> it cannot see. A project extension **must** be a schema the project owns. (Packaged `bio.*`
> extensions belong to **commons** records, which carry their own `schema_profile` and never come
> through `entity_extensions`.)

**Interfaces:**
- Produces `resolve_profile(kind: str, *, extensions: list[str], loader: SchemaLoader | None) -> ProfileString`
  — the default base+mixin plus the project's declared extensions, each certified against the root
  contract. **Tasks 7, 9 and 10 call this, not `default_profile_for_kind`.**
  (`default_profile_for_kind` remains the zero-extension case, and `resolve_profile(kind,
  extensions=[])` is required to equal it exactly.)
- Produces `load_project_schema(project_root) -> ProjectSchema` (`.validator`, `.profile_for(kind)`)
  — the **project boundary**. It binds the profile to a loader that can find the project's schemas,
  because a profile resolved *with* extensions but validated through a package-only loader raises
  `SchemaNotFoundError` on a schema the project does own. **It certifies every declared entry
  eagerly**: malformed component, unknown kind, missing file, broken root contract. A stanza is a
  *claim* about how this project's entities are validated — and `hypothsis:`, one letter out, would
  otherwise sit in `science.yaml` forever, matching no kind, validating nothing, and **looking
  exactly like a project whose fields are protected.**

- [x] **Step 1: Write the failing test**

```python
# science/model/tests/test_project_extensions.py
def test_an_extension_ADDS_a_field_without_touching_the_core_mixin(tmp_schema_dir) -> None:
    _write_extension(tmp_schema_dir, "extension-mm30-assessment-1.0.json", {
        "properties": {"confidence_mechanistic_label": {"type": "string"}}
    })
    profile = resolve_profile("hypothesis", extensions=["mm30.assessment/1.0"])
    EntityValidator(SchemaLoader(project_dir=tmp_schema_dir)).validate_as(
        _h(confidence_mechanistic_label="high"), profile
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("confidence_mechanistic_label", "high"),          # mm30
        ("identification", "t(4;14)"),                     # mm30
        ("external_hypothesis_id", "EH-042"),              # evolution
        ("source_stated_evidence", "barcoded mouse expt"), # evolution -- the RENAME TARGET
    ],
)
def test_the_SAME_field_is_rejected_WITHOUT_the_extension(field: str, value: str) -> None:
    # This is the whole point: each field is legal for exactly ONE project and illegal everywhere
    # else. If any of these passes without its extension, the mixin swallowed a project field --
    # the defect Task 2 removed nine keys to prevent.
    #
    # `source_stated_evidence` is here because it is the ONLY field in the corpus that Task 9
    # CREATES. Every other key is either already authored or already forbidden; this one is written
    # by the migration itself, so if core silently admitted it, the migration would appear to
    # succeed everywhere and the extension would be dead code that nobody noticed was dead.
    with pytest.raises(EntityValidationError):
        EntityValidator().validate_as(_h(**{field: value}), default_profile_for_kind("hypothesis"))


def test_an_extension_may_NOT_redefine_a_core_field(tmp_schema_dir) -> None:
    # Additive ONLY (design §6). An allOf can only narrow, so a redefinition would silently
    # INTERSECT with the core enum rather than replace it -- producing an unsatisfiable schema
    # rather than an error. Catch it at load, loudly.
    _write_extension(tmp_schema_dir, "extension-bad-x-1.0.json", {
        "properties": {"status": {"enum": ["whatever"]}}
    })
    with pytest.raises(ExtensionRedefinesCoreField, match="status"):
        resolve_profile("hypothesis", extensions=["bad.x/1.0"],
                        loader=SchemaLoader(project_dir=tmp_schema_dir))


def test_the_evolution_extension_declares_BOTH_of_its_fields(tmp_schema_dir) -> None:
    # `external_hypothesis_id` (evicted from core) and `source_stated_evidence` (the rename target of
    # `author_stated_evidence`). Two projects, two extensions -- and 13 + 13 authored values that
    # vanish the moment the schema closes if either is missing.
    _write_extension(tmp_schema_dir, "extension-evolution-provenance-1.0.json", {
        "properties": {
            "external_hypothesis_id": {"type": "string", "pattern": "^EH-[0-9]+$"},
            "source_stated_evidence": {"type": "string", "pattern": "\\S"},
        }
    })
    profile = resolve_profile("hypothesis", extensions=["evolution.provenance/1.0"],
                              loader=SchemaLoader(project_dir=tmp_schema_dir))
    V = EntityValidator(SchemaLoader(project_dir=tmp_schema_dir))
    V.validate_as(_h(external_hypothesis_id="EH-042",
                     source_stated_evidence="established in barcoded mouse experiments"), profile)


def test_the_OLD_key_is_dead_even_WITH_the_extension(tmp_schema_dir) -> None:
    # THE test that makes the rename a rename. `author_stated_evidence` is `false` in the core mixin,
    # and `false` inside an allOf is absolute -- no extension can re-admit it. If this ever passes,
    # the corpus has two spellings of one field and the migration silently became optional.
    _write_extension(tmp_schema_dir, "extension-evolution-provenance-1.0.json", {
        "properties": {"source_stated_evidence": {"type": "string"}}
    })
    profile = resolve_profile("hypothesis", extensions=["evolution.provenance/1.0"],
                              loader=SchemaLoader(project_dir=tmp_schema_dir))
    with pytest.raises(EntityValidationError):
        EntityValidator(SchemaLoader(project_dir=tmp_schema_dir)).validate_as(
            _h(author_stated_evidence="established (barcoded mouse experiment)"), profile
        )
```

> The third test is the one that matters. Because composition is a pure `allOf`, an extension
> redefining `status` does **not** override the core enum — it **intersects** with it, yielding a
> schema nothing can satisfy. The failure would surface as *"this valid file is invalid"* with no
> hint why. **Reject redefinition at load time**, by name.

**And the tests the root contract requires, which the block above does not reach** — a
`properties`-only check passes every one of these, so each is a distinct hole
(`test_project_extensions.py` / `test_entity_profiles.py`):

| test | the hole it closes |
|---|---|
| `test_a_root_applicator_cannot_narrow_the_composed_record` (7 params: `required`, `not`, `if`, `additionalProperties`, `$ref`, `allOf`, `dependentRequired`) | each narrows the composed record **without naming a core field** |
| `test_an_extension_MAY_require_a_field_it_owns` | the **control** — a project *is* entitled to require its own field |
| `test_two_extensions_may_not_both_own_one_field` | two owners → constraints silently intersect |
| `test_an_extension_may_not_redefine_a_BASE_field_either` | the check must span **both** allOf branches, not just the mixin |
| `test_a_project_schema_dir_does_not_shadow_a_PACKAGE_schema` | a project redefining the core **kind** for itself |
| `test_a_MISSPELLED_kind_is_an_error_not_a_silent_no_op` | `hypothsis:` — a stanza nobody reads |
| `test_a_declared_extension_with_NO_schema_file_is_an_error` | declared, never written |
| `test_a_project_extension_does_NOT_fall_back_to_a_PACKAGED_schema` | the ownership ruling, made executable |
| `test_zero_extensions_is_exactly_the_default_profile` | `resolve_profile` must not fork from the default |

- [x] **Step 2: Run and fail.**

- [x] **Step 3: Implement — four pieces, each closing a way the contract could be believed but not held.**

  1. **`SchemaLoader(project_dir: Path | None)`** consults `project_dir` **only when
     `is_extension(component)`**, then falls back to `importlib.resources`. A base or a mixin is
     **never** read from a project dir (see the box above — that is how a project would redefine the
     core kind for itself).
  2. **`resolve_profile(kind, *, extensions, loader)`** in the new `resolve.py`. For each component:
     `_certify_root_contract` (the allow-list; `required ⊆ owned`; `type: object`), then **no
     collision with base or mixin `properties`** (`ExtensionRedefinesCoreField`), then **no second
     owner for any field** (`ExtensionContractError`). With `extensions=[]` it must return exactly
     `default_profile_for_kind(kind)` — it is not permitted to become a second, subtly different
     spelling of the default, since 20 of the 22 projects go through it declaring nothing.
  3. **`entity_extensions: dict[str, list[str]]` as a DECLARED field on `ProjectConfig`.** It is
     `extra="allow"`, so an undeclared stanza parses, is ignored, and does nothing.
  4. **`load_project_schema(project_root)`** — the project boundary. It pairs the validator with a
     project-aware loader, and **certifies every declared entry eagerly**: malformed component →
     unknown kind → missing file → root contract. Nothing about a declaration may wait until some
     entity happens to be validated.

```yaml
entity_extensions:
  hypothesis: ["mm30.assessment/1.0"]   # resolves to schemas/extension-mm30-assessment-1.0.json
```

> **`entity_schema_version: 2` is NOT set here — Task 9 sets it, per repo, in the same commit that
> rewrites the files.** The flag is what *arms* `validate_as` and `unevaluatedProperties: false` for
> a project. Setting it now would arm strictness against a corpus that still authors `phase` (every
> file) and `author_stated_evidence` (13 files) — both `false` in the mixin — so **`science validate`
> would fail on all 25 hypotheses in these two repos, and stay failing until Task 9 lands.** The
> extension file and the `entity_extensions` stanza are **inert at version 1**: they may land now,
> and must, because Task 9 cannot migrate a field whose owner does not yet exist.

- [x] **Step 4: Green — the model suite.** That is the whole gate for this task.

> ### The corpus gate CANNOT run here — and putting it here is what would have broken the migration
>
> An earlier draft of this step demanded a two-sided dry run in both projects: *"with the extension,
> `science validate` exits 0; without it, the files fail loudly."* **The first half is impossible at
> this point in the plan, for both projects.** Task 6 makes `phase` `false` and every one of the 25
> files still authors it; Task 6 makes `author_stated_evidence` `false` and Task 9 is what renames
> it. So the green half could only be reached by *not* arming version 2 — in which case nothing is
> being validated and the run proves nothing — or by arming it and watching all 25 files fail.
>
> **The negative half is the half that belongs at this task, and it is already here**, at unit
> level: `test_the_SAME_field_is_rejected_WITHOUT_the_extension` proves each of the four fields is
> illegal in core, which is the *only* claim Task 6b actually makes. The positive half — *these
> exact files validate* — is a claim about **migrated** frontmatter, which does not exist until
> Task 9 renders it. It is gated by the **two-phase preflight in Task 11**, over all 147 files, and
> both projects appear there by name.
>
> *A task must be gated by a check that can pass. A check that cannot pass yet is not a gate — it
> is an instruction to the implementer to skip it, and the one thing they will remember is that
> this step is skippable.*

- [x] **Step 5: Commit — THREE repos, separately:** the toolkit, mm30, and **evolution**
  (`~/d/cancer/mechanisms/evolution` — the project that owns 13 of the corpus's hypotheses and every
  file in the belief cluster, and which this plan managed not to list at all until Task 1 derived it).
  Each project repo gets **the extension schema + the `entity_extensions` stanza, and nothing
  else** — no `entity_schema_version`, so the commit is behavior-neutral there and `science validate`
  keeps passing exactly as it does today.

> ### Behavior-neutrality was MEASURED, not asserted — and it exposed the delivery channel
>
> `science validate` was run in both repos with and without the new stanza: **evolution 70 findings
> → 70; mm30 216 → 216.** Byte-identical. The extension schema and the `entity_extensions` stanza
> are inert at version 1, exactly as this step claims.
>
> The measurement turned up something the plan had not registered. **Both repos install the toolkit
> from the public Git source** (`science = { git = "https://github.com/khughitt/science.git" }`,
> revision pinned in `uv.lock`) — *not* from a local path. So a consumer project does not see this
> branch's work until it is **pushed and re-pinned**. Two consequences, both load-bearing for the
> tasks ahead:
>
> - Evolution's 11 `[status-vocabulary]` ERRORs (and mm30's) are **pre-existing**, produced by the
>   pinned revision's *uncertified* status check — the very defect this branch's first commit
>   (`e462b5f7`) fixes. They are not caused by Task 6b, and they will not clear in the consumer
>   repos until the branch ships.
> - **Task 11's corpus preflight cannot run against the pinned toolkit.** It must run against this
>   branch's `science` — either from the toolkit checkout, or after the consumers re-pin. A preflight
>   run against the Git-pinned revision would be validating the corpus with a toolkit that has
>   neither `mixin-hypothesis-1.0` nor `entity_extensions`, and would pass while proving nothing.

> ### What this task's FIRST draft got wrong — corrected in place above, not appended below
>
> The executable text above **is** the contract; there is no second one. Recorded here only so the
> same four mistakes are not re-derived: it spelled the extension filenames with a **dot** (the
> loader has always flattened dots to hyphens — those files would never have been found); it put
> `resolve_profile` in `profile.py` (**cyclic**); it said "search `project_dir` first" full stop
> (which lets a project **redefine the core kind for itself**); and it said `minLength: 1` (**a
> single space has length 1** — the very defect Task 6 had already been corrected for).
>
> A fifth was found on review, and it is the sharpest: **checking `properties` against core does not
> enforce "additive only" at all.** `required: ["verdict"]`, `not`, `if`/`then`,
> `additionalProperties`, `$ref` and `dependentRequired` each narrow the composed record **from
> inside the extension's own allOf branch, without ever naming a core field** — so a
> `properties`-clean extension sailed through. Hence the **allow-list** root contract above. *A
> contract enforced on one keyword is a contract enforced on nothing.*

> ### mm30's three labels are typed and non-empty, but NOT enum-locked — **RULED BY THE OWNER 2026-07-13**
>
> *"Keep the three labels non-empty strings for now. Do not infer an enum from twelve observations;
> closing that vocabulary belongs to its owner."*
>
>
> The corpus is perfectly consistent — `confidence_label` and `confidence_mechanistic_label` are
> each one of `{high, moderate, low}`, and `identification` is `observational` (11) or
> `methodological` (1). Enum-locking was tempting and is **not** what shipped.
>
> A vocabulary is only enforceable once its **owner** has ruled on it, and mm30's author has not.
> Enum-locking on 12 observations would be enforcing an **uncertified vocabulary** — precisely how
> the status check earlier in this same arc broke `validate` across five projects and produced 472
> findings. `pattern: "\S"` is a real contract (the field must be present and say something); the
> closed vocabulary is a **one-line change to a project-owned file** whenever mm30 wants to make it.
> That it can be made *there*, without touching the toolkit, is what ownership is for.

---

### Task 7: `resolution.py` — the cross-record layer, **wired**

Schema validates **one record in isolation**. It cannot resolve a successor ID. **Presence is
schema; resolution is a validator.** Without this, a *present but dangling* `superseded_by:`
satisfies the schema and closes the entity with no real reason behind it — the hole in a subtler
dress.

> **Scope — ONE load-time invariant, not two.** Design §7.4 listed three cross-record invariants.
> Rev 1 claimed all three and implemented one; rev 2 deferred the third; and rev 3's *"two at load
> time: successor resolution **and archive-record existence**"* is **now down to one, because the
> second no longer exists.** `archive_ref` was **deleted** in Task 6: it appears in zero source
> files, is authored by zero corpus files, and — decisively — **has no resolvable namespace**, since
> `archive.py` keys its index by the archived entity's **own id** (`ArchiveIndex.active_by_id`) and
> mints no record identifier. There is nothing on the other end of the reference to confirm the
> existence of. An archived entity's archive record is already reachable **from its `id` alone**.
> **`archived` now requires `closure_basis`, exactly like `retired`, and this module never
> constructs `known_archive_refs`.**
>
> So: **lineage is the sole load-time resolution invariant** — `superseded_by` and
> `resynthesized_into` must resolve to a real, live, local entity that is not the entity itself.
> The third invariant — **every authored verdict has qualifying, resolvable evidence** — is a
> **graph-time** fact (it needs evidence-line edges, which exist only after materialization), so it
> ships as a **graph check** (Step 3c below), not here.
>
> **And its trigger is corrected (design rev 8).** Rev 2 scoped it to `status: complete`. **Wrong
> — it applies to EVERY authored verdict.** A `draft` hypothesis asserting `verdict: refuted` with
> no evidence behind it is a fabrication whatever its lifecycle says; gating on `complete` would
> have left the front door open. **`verdict` is an evidence-constrained adjudication** (rev 8's
> contract), and the constraint is not conditional on the lifecycle.

> ### ⚠️ A CHECK CANNOT SHIP BEFORE THE SURFACE IT OBSERVES — three of this task's claims were inert
>
> Task 6 established the rule when the packet `$def` and its model fields had to move together:
> *"schema and model move together" names **the window in which the corpus is broken**, and the
> window has to be zero.* The same rule, applied to a **check**, says: **a check and the surface it
> reads ship in the same commit.** A check that runs against a surface which does not exist yet does
> not fail — **it passes, silently, on nothing.** That is the silent instrument this entire arc
> exists to abolish, and it is *worse* than no check, because its green reads as coverage.
>
> Three of this task's claims were exactly that, and the fix is to **pull the substrate forward, not
> to push the checks back** — the checks are the deliverable:
>
> | inert claim | surface it needs | was landing in | now lands in |
> |---|---|---|---|
> | the lineage check reads `superseded_by` / `resynthesized_into` / `closure_basis` / `verdict` | those four fields **on `HypothesisEntity`** — the model drops them today, so the check would inspect already-projected entities and see **nothing** | Task 8 | **here** (Step 3a) |
> | the verdict-agreement **graph** check | **`sci:verdict` in the graph** — materialization emits `projectStatus` and `disposition`, and no verdict at all, so the check reads `None` for every hypothesis and finds no disagreement, ever | Task 10 | **here** (Step 3b) — *emission only; the `sci:disposition` **deletion** stays in Task 10, where `attention.py` is rewired* |
> | the write boundary refuses a dangling successor | **a write boundary** — `edit_entity` validates nothing today (`entities.py:935`), so there is nothing here to hang the guard on | here | **Task 10**, which ships that boundary. *(It is tested on `resynthesized_into`: `superseded_by` is derived from resolvable edges and cannot dangle.)* |
>
> The `edit_entity` guard is the one that moves *out*: Task 10 already ships that boundary, its
> atomic `closure_basis` contract and its test. Task 7 stops claiming a call site it cannot build.

**Files:**
- Create: `science/model/src/science_model/entity_schema/resolution.py`
- **Modify: `science/model/src/science_model/entities.py` (`HypothesisEntity`)** — the four
  projection fields (`verdict`, `closure_basis`, `superseded_by`, `resynthesized_into`), **moved
  forward from Task 8**: the lineage check below cannot observe what the model drops.
- **Modify: `science/src/science_tool/graph/materialize.py:646`** — emit `sci:verdict` beside
  `sci:projectStatus`. **Additive only.**
- Modify: `validate/checks/hypotheses.py` — the check builds the resolver and calls
  `check_resolution`. **`graph/sources.py` is NOT modified: the loader must not build a resolver**
  (Step 3b's box — it makes an alias collision unloadable rather than reportable).
- Test: `science/tests/test_loader_resolver_boundary.py` — the AST guard that keeps it that way.
- Create: `science/src/science_tool/validate/checks/verdict_agreement.py`
- Test: `science/model/tests/test_resolution.py`, `science/tests/test_resolution_wiring.py`,
  **`science/tests/test_verdict_agreement.py`** (Step 3c-i — the verdict subsystem had **no** tests
  at all, and its artifact diff is empty by construction, so it could not have had them)

- [x] **Step 1: Write the failing tests** — unit **and wiring**. Rev 1 shipped the module unwired
  and admitted it in its own self-review. **The wiring tests are the point.**

```python
# science/model/tests/test_resolution.py
from dataclasses import dataclass, field

from science_model.entity_schema.resolution import check_resolution


@dataclass(frozen=True)
class _Res:
    status: str
    canonical_id: str | None = None
    candidates: tuple[str, ...] = field(default_factory=tuple)


class _Targets:
    """A stand-in with ReferenceResolver's EXACT semantics: alias -> canonical, else unresolved.

    The real wiring passes the real `ReferenceResolver` (Step 3a). This exists so the unit tests can
    state each alias case in one line -- NOT so they can invent a different resolution rule. If the
    two ever disagree, the wiring test (`test_resolution_wiring.py`, real resolver, real corpus) is
    the authority.
    """

    def __init__(self, aliases: dict[str, str]) -> None:
        self._aliases = aliases

    def resolve(self, raw: str) -> _Res:
        canonical = self._aliases.get(raw)
        if canonical is None:
            return _Res(status="unresolved")
        return _Res(status="resolved", canonical_id=canonical)


# `0009` is an ALIAS of the live `0009-successor`; `0003-gone` resolves but is ARCHIVED.
TARGETS = _Targets({
    "hypothesis:0001-x": "hypothesis:0001-x",
    "hypothesis:0002-y": "hypothesis:0002-y",
    "hypothesis:0009": "hypothesis:0009-successor",       # <- the alias
    "hypothesis:0009-successor": "hypothesis:0009-successor",
    "hypothesis:0003-gone": "hypothesis:0003-gone",       # <- resolves, but NOT live
    "hypothesis:x-alias": "hypothesis:0001-x",            # <- an alias OF the entity itself
})
LIVE_HYPOTHESES = {"hypothesis:0001-x", "hypothesis:0002-y", "hypothesis:0009-successor"}


def _check(entity: dict[str, object]):
    return check_resolution(entity, targets=TARGETS, live_hypotheses=LIVE_HYPOTHESES)


def test_dangling_successor_is_caught() -> None:
    # The whole reason this module exists: the schema is satisfied, the entity is closed,
    # and the reason it closed does not exist.
    #
    # NOTE the assertions are on FIELDS. `check_resolution` returns `list[ResolutionViolation]`,
    # and `"9999-nope" in v[0]` -- what rev 1 wrote -- is not a substring test on a Pydantic model:
    # `__iter__` yields (field_name, value) PAIRS, so the expression is simply False and the test
    # would fail against a CORRECT implementation. That is the cost of a typed carrier, and it is
    # the point of one: the violation's parts are addressable instead of buried in a sentence.
    v = _check({"id": "hypothesis:0001-x", "status": "superseded",
                "superseded_by": "hypothesis:9999-nope"})
    assert len(v) == 1
    assert v[0].entity_id == "hypothesis:0001-x"
    assert v[0].field == "superseded_by"
    assert v[0].ref == "hypothesis:9999-nope"


def test_resolving_successor_passes() -> None:
    assert _check({"id": "hypothesis:0001-x", "status": "superseded",
                   "superseded_by": "hypothesis:0002-y"}) == []


def test_a_LIVE_ALIAS_resolves_and_is_CLEAN() -> None:
    # ☠️ The case raw membership BLOCKS. `hypothesis:0009` is an alias of the live
    # `hypothesis:0009-successor`; it is a perfectly good successor, and `ref not in known_ids`
    # would have called it dangling and refused a CORRECT corpus.
    assert _check({"id": "hypothesis:0001-x", "status": "superseded",
                   "superseded_by": "hypothesis:0009"}) == []


def test_a_SELF_ALIAS_is_caught() -> None:
    # ☠️ The case raw `ref == entity_id` MISSES. `hypothesis:x-alias` is an alias OF
    # `hypothesis:0001-x`, so as a STRING it differs from the entity's id, resolves cleanly, and
    # sails through as a valid successor -- a closed loop, wearing the check's green.
    # Identity must be decided AFTER resolution, on canonical ids, on both sides.
    v = _check({"id": "hypothesis:0001-x", "status": "superseded",
                "superseded_by": "hypothesis:x-alias"})
    assert len(v) == 1
    assert "itself" in v[0].message


def test_an_ARCHIVED_target_RESOLVES_and_is_still_a_violation() -> None:
    # Resolution and liveness are TWO questions. `0003-gone` resolves perfectly -- and naming a
    # dead entity as the reason you closed is not a reason.
    v = _check({"id": "hypothesis:0001-x", "status": "superseded",
                "superseded_by": "hypothesis:0003-gone"})
    assert len(v) == 1
    assert "not a live hypothesis" in v[0].message


def test_resynthesized_into_is_a_LIST_and_every_member_must_resolve() -> None:
    # One good member does not discharge the list. A resolver that returned on first success --
    # or that reported the FIELD rather than the REF -- passes a suite that only counts findings.
    # The typed carrier is what lets this assert WHICH member dangled.
    v = _check({"id": "hypothesis:0001-x", "status": "superseded",
                "resynthesized_into": ["hypothesis:0002-y", "hypothesis:9999-nope"]})
    assert len(v) == 1
    assert v[0].field == "resynthesized_into"
    assert v[0].ref == "hypothesis:9999-nope"       # the BAD member, not the good one


def test_self_supersession_is_caught() -> None:
    # The literal spelling. Kept BESIDE the alias case above, not replaced by it: they fail
    # differently, and a check that catches one is not a check that catches the other.
    v = _check({"id": "hypothesis:0002-y", "status": "superseded",
                "superseded_by": "hypothesis:0002-y"})
    assert len(v) == 1
    assert v[0].entity_id == "hypothesis:0002-y"
    assert "itself" in v[0].message


def test_an_ARCHIVED_entity_has_NOTHING_to_resolve() -> None:
    # `archived` is NOT in `_TERMINALS_WITH_STRUCTURE` (design §7.4, corrected): the archive index
    # mints no record id, so there is nothing a ref could point at. It is discharged by
    # `closure_basis` -- which is SHAPE, and shape is Task 6's. This module must not restate it.
    assert _check({"id": "hypothesis:0001-x", "status": "archived",
                   "closure_basis": "folded into h5"}) == []


def test_a_basis_closed_entity_needs_no_structure() -> None:
    assert _check({"id": "hypothesis:0001-x", "status": "superseded",
                   "closure_basis": "folded into h5"}) == []


def test_a_live_entity_is_not_checked() -> None:
    assert check_resolution(
        {"id": "hypothesis:0001-x", "status": "active"}, targets=TARGETS, live_hypotheses=set()
    ) == []
```

```python
# science/tests/test_resolution_wiring.py
def test_validate_reports_a_dangling_successor(tmp_project) -> None:
    write_hypothesis(tmp_project, "0001-x", status="superseded",
                     extra={"superseded_by": "hypothesis:9999-nope"})
    findings = [r for r in run_validate(tmp_project) if r.rule == "hypothesis.dangling-lineage"]
    assert len(findings) == 1
    # WARN, hard-coded, until the kind is certified. Task 12 Step 2b routes this emitter through
    # `severity_for_kind` and `test_dangling_lineage_FLIPS_to_error_with_the_kind` inverts this
    # exact assertion -- so if that step is skipped, THAT test fails. The promise has a test now,
    # not a comment: rev 1 pointed at Task 12, and Task 12 graded only `status-vocabulary`.
    assert findings[0].severity == "warn"
    assert "9999-nope" in findings[0].message
```

> ### ⚠️ The resolution cases must be re-tested through the REAL loader, not just the stub
>
> `_Targets` in the unit test proves `check_resolution`'s *logic*. It proves **nothing about the
> resolver the loader actually builds** — and that construction is where the wiring can silently
> rot. Drop `manual_aliases=` from `ReferenceResolver.from_entities` and every unit test still
> passes, because the stub was never wired to it.
>
> **Worse, a count-only assertion hides it.** Omit `manual_aliases` and an archived successor stops
> resolving — so it becomes an *unresolved* violation instead of a *not-live* one. **Still one
> finding. Still green.** The test must assert the **message**, which is the only thing that
> distinguishes "the resolver could not find it" from "the resolver found it, and it is dead."
>
> #### `identity_table=` is passed for parity, and is NOT pinned by any test. Say so.
>
> An earlier draft claimed a scoped-successor test pinned it. **That test could not have run** — the
> schema's `^hypothesis:` pattern rejects `demo:hypothesis:0002-y` before the resolver ever sees it.
>
> And no test *can* pin it, because for a lineage ref `identity_table` is provably **inert**:
> `identity_table` feeds only `owner_scopes` / `scope_names` / `owner_scopes_by_root`, so it changes
> an answer only via `scope_ambiguous` — which needs an id owned in **two** owner scopes. A load has
> exactly **one** project scope (`classify_owner_scope`, identity_table.py:96), so the second scope
> can only be `commons` — and **commons owns no hypotheses** (274 paper, 41 dataset, 40 topic, 14
> theme, 0 hypothesis). A `hypothesis:` id therefore has exactly one owner scope, always.
>
> It is passed anyway, because **`materialize.py:348` passes it**, and materialize is what builds the
> lineage edges. Its inertness rests on what commons currently *contains* — data, not contract — and
> a check whose correctness depends on that is the same fragility as the raw-`known_ids` set this
> task replaced. **Parity with the materializer is the invariant; keep the argument.**
>
> Note the codebase does **not** already have one canonical construction: of the seven
> `ReferenceResolver.from_entities` call sites, only `materialize.py:348` passes `identity_table`.
> Do not "harmonize" the other six as a drive-by — they resolve different things.

```python
def test_a_LIVE_ALIAS_resolves_through_the_REAL_loader(tmp_project) -> None:
    # `aliases:` frontmatter -> `build_alias_map` (sources.py:656). Raw membership on a set of ids
    # would call this dangling and REFUSE A CORRECT CORPUS.
    write_hypothesis(tmp_project, "0002-y", aliases=["hypothesis:0002"])
    write_hypothesis(tmp_project, "0001-x", status="superseded",
                     extra={"superseded_by": "hypothesis:0002"})
    assert lineage_violations(tmp_project) == []          # the CHECK, not the loader


def test_a_SELF_ALIAS_is_caught_through_the_REAL_loader(tmp_project) -> None:
    # An alias OF the entity, written ON the entity. As a STRING it differs from the id, so the
    # `ref == entity_id` check never fires; it resolves cleanly and reads as a valid successor.
    write_hypothesis(tmp_project, "0001-x", status="superseded", aliases=["hypothesis:x-alias"],
                     extra={"superseded_by": "hypothesis:x-alias"})
    violations = lineage_violations(tmp_project)          # the CHECK, not the loader
    assert len(violations) == 1
    assert "itself" in violations[0].message


def test_an_ARCHIVED_successor_RESOLVES_and_is_still_a_violation(tmp_project) -> None:
    # ☠️ THE test that pins `manual_aliases=`. Archived ids are folded into `manual_aliases`
    # (sources.py:618) and are deliberately NOT loaded as live entities -- so an archived successor
    # RESOLVES and is absent from `live_hypotheses`.
    #
    # Assert the MESSAGE, not the count. Omit `manual_aliases=` from `from_entities` and this ref
    # simply fails to resolve: still exactly one violation, still green, and the wiring defect is
    # invisible. The message is the only witness that the resolver FOUND it and found it DEAD.
    write_hypothesis(tmp_project, "0003-gone")
    archive_entity(tmp_project, "hypothesis:0003-gone")        # index-only; markdown not loaded
    write_hypothesis(tmp_project, "0001-x", status="superseded",
                     extra={"superseded_by": "hypothesis:0003-gone"})
    violations = lineage_violations(tmp_project)          # the CHECK, not the loader
    assert len(violations) == 1
    assert "not a live hypothesis" in violations[0].message  # NOT "does not resolve"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("superseded_by", "demo:hypothesis:0002-y"),
        ("resynthesized_into", ["demo:hypothesis:0002-y"]),
    ],
)
def test_a_SCOPED_lineage_ref_is_REJECTED_BY_THE_SCHEMA(
    field: str, value: str | list[str]
) -> None:
    # Lineage is UNSCOPED. `superseded_by` and `resynthesized_into` are `pattern: "^hypothesis:"`
    # (mixin-hypothesis-1.0.json:27,31), so `demo:hypothesis:0002-y` never reaches the resolver --
    # it fails schema validation first.
    #
    # This test exists because an earlier draft asserted the OPPOSITE: that a scoped successor
    # resolves cleanly through the loader. That test could not have passed. Rather than widen the
    # pattern to keep it alive -- tuning the contract to serve a test -- the ban is made EXPLICIT
    # here, and it is what the corpus already says: ZERO hypotheses author lineage at all, and ZERO
    # scoped refs (`scope:kind:slug`) exist anywhere in the 18 roots.
    with pytest.raises(EntityValidationError):
        validate_hypothesis(
            _hypothesis(id="hypothesis:0001-x", status="superseded",
                        **{field: value})
        )


def test_the_dangling_lineage_rule_is_NOT_GATED_yet(tmp_project) -> None:
    # WARN that fails no build. The rule's absence from every gate tier is the whole content of
    # "ungated" -- and it is the claim Task 12 later inverts, so it needs to be pinned HERE.
    from science_tool.validate.gates import cumulative_rules

    assert "hypothesis.dangling-lineage" not in cumulative_rules("hygiene")


def test_the_LOADER_can_actually_SEE_the_terminal_fields(tmp_project) -> None:
    # The test that would have caught the inert wiring. `check_resolution` reads PROJECTED
    # entities, and `HypothesisEntity` dropped all four terminal fields until Step 3 -- so the
    # check would have inspected a stripped record, found no reference, and reported clean.
    # Assert the SUBSTRATE, not just the finding: a green resolver over a blind loader is the
    # silent instrument this arc exists to abolish.
    from science_model.entities import HypothesisEntity

    for field in ("verdict", "closure_basis", "superseded_by", "resynthesized_into"):
        assert field in HypothesisEntity.model_fields, f"{field}: the check cannot see what the model drops"

    write_hypothesis(tmp_project, "0001-x", status="superseded",
                     extra={"superseded_by": "hypothesis:9999-nope"})
    sources = load_project_sources(tmp_project)

    # `ProjectSources.entities` is a LIST[Entity], not a mapping (sources.py:155).
    entity = next(e for e in sources.entities if e.id == "hypothesis:0001-x")
    assert entity.superseded_by == "hypothesis:9999-nope"   # it SURVIVED the projection

    # ...and the CHECK, reading those projected entities through the real resolver, SAW it.
    assert ["9999-nope" in v.message for v in lineage_violations(tmp_project)] == [True]
```

> The write-boundary refusal has **moved to Task 10** — `edit_entity` validates nothing today
> (`entities.py:935`), so there was no boundary here to hang a guard on. **Task 7a splits that
> boundary into a private `_prepare_write` / `_commit_write` pair** and adds the derived writer
> `consolidation._prepare_supersession` on top of it (the operation leg of the D4 triangle:
> `mark_superseded` must write the inverse it derives). **Task 10 adds the ENFORCEMENT** inside
> `_prepare_write`, so *both* entry points inherit it — schema validation, the atomic
> `closure_basis` contract, and the dangling-successor refusal. `edit_entity` never gains a
> `superseded_by` parameter, and neither does the derived writer: **it takes the graph and reads the
> superseder off the canonical edge.** A derived field with any caller-supplied spelling — authored
> or not — is the thing rev 10 deleted.

- [x] **Step 2: Run and fail.**

- [x] **Step 3: The four projection fields — MOVED FORWARD from Task 8.** Without them the loader
  pass below reads a stripped record. `science/model/src/science_model/entities.py`,
  `HypothesisEntity`:

```python
    verdict: Literal["partially-supported", "supported", "weakened", "refuted"] | None = None
    closure_basis: str | None = None
    superseded_by: str | None = None
    resynthesized_into: list[str] = Field(default_factory=list)
```

  Task 8 still owns their **certification** (the reconciliation battery against the schema); this
  task owns their **existence**, because it is the first task that reads them.

- [x] **Step 3a: Implement `resolution.py`**

```python
# science/model/src/science_model/entity_schema/resolution.py
"""Cross-record invariants — the D3 escape hatch, ENUMERATED.

JSON Schema is the authority for a record's SHAPE and for the PRESENCE of a structural basis.
It validates one record in isolation, so it structurally cannot answer the ONE cross-record
question this layer exists for: does this LINEAGE reference resolve to a real, live entity that
is not the entity itself?

That is the whole list. It is deliberately a CLOSED one rather than an open-ended second
authority (design §9, D3). Getting the split wrong re-opens the hole it was built to close: a
PRESENT but DANGLING `superseded_by:` satisfies the schema, closes the entity, and records no
real reason for the closure.

NOT HERE, and neither is an oversight:

  * "does an archive record exist?" -- there is NO SUCH RECORD to exist. `archive_ref` was
    deleted: the archive index is keyed by the archived entity's own id and mints no record
    identifier, so there is nothing on the other end of such a reference. `archived` is
    discharged by `closure_basis`, which is SHAPE, and shape is the schema's.
  * "does a verdict have qualifying evidence?" -- that needs the evidence-line EDGES, which
    exist only after materialization. It is a graph-time invariant and this runs at load time;
    it belongs to a graph check. Said plainly so nobody assumes it is covered here.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

# `superseded` is the ONLY terminal with resolvable structure (design §7.4, corrected 2026-07-13).
# `archived` was in this set for two revisions and had NO archive check behind it -- because none
# can be written: the archive index is keyed by the archived entity's own id and mints no record
# identifier, so there is nothing to resolve. A status listed here with no check is a promise the
# module does not keep. `retired` and `archived` are discharged by `closure_basis`, which is SHAPE,
# and shape is Task 6's -- this module must not restate it.
_TERMINALS_WITH_STRUCTURE = frozenset({"superseded"})


class ResolutionViolation(BaseModel):
    """One cross-record failure, typed -- the contract between checker, loader and validation.

    A bare `list[str]` would have forced `validate/` to re-parse a sentence to recover the id and
    the field it needs for a `Result`. The message is for humans; these fields are for code.
    """

    entity_id: str
    field: str          # "superseded_by" | "resynthesized_into"
    ref: str
    message: str


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


# ⚠️ LAYERING. `ReferenceResolver` lives in `science_tool.graph.reference_resolution`, and
# `science_tool` depends on `science_model` -- NOT the other way round. Importing it here would
# invert the package dependency and make the two cyclic. So this module states what it NEEDS,
# structurally, and `science_tool` passes the real resolver in. `ReferenceResolver` satisfies both
# protocols as-is (extra keyword-only params with defaults are compatible), so there is nothing to
# adapt and no second implementation to keep in step.
class Resolved(Protocol):
    status: str                       # "resolved" | "unresolved" | "scope_ambiguous" | "tag"
    canonical_id: str | None
    candidates: tuple[str, ...]


class LineageTargets(Protocol):
    """What this module needs of a resolver. `ReferenceResolver` satisfies it as-is."""

    def resolve(self, raw: str) -> Resolved: ...


def check_resolution(
    entity: dict[str, Any], *, targets: LineageTargets, live_hypotheses: set[str]
) -> list[ResolutionViolation]:
    """Cross-record terminal violations. Empty == clean.

    RESOLUTION only. Whether a basis is PRESENT and NON-EMPTY is shape, and shape is the schema's
    (Task 6: `minItems: 1`, `pattern: "\\S"`). Re-checking it here would be a second authority for
    the same fact, which is the collapse this arc exists to undo.

    RESOLVE, then CHECK -- in that order, and never `raw in some_set`. See the box below.
    """
    if entity.get("status") not in _TERMINALS_WITH_STRUCTURE:
        return []

    raw_id = str(entity.get("id") or "<unknown>")
    # The entity's OWN id must go through the same resolver, or a self-reference written in any
    # spelling other than the canonical one slips past the identity check below.
    self_res = targets.resolve(raw_id)
    self_canonical = self_res.canonical_id if self_res.status == "resolved" else raw_id

    violations: list[ResolutionViolation] = []

    for field, ref in _lineage_refs(entity):
        resolution = targets.resolve(ref)

        if resolution.status == "scope_ambiguous":
            message = (
                f"{raw_id}: {field} -> {ref!r} is owned in more than one loaded scope "
                f"({', '.join(resolution.candidates)}); a scoped form is required"
            )
        elif resolution.status != "resolved" or resolution.canonical_id is None:
            message = (
                f"{raw_id}: {field} -> {ref!r} does not resolve to any known entity; "
                f"the entity is closed and the reason it closed does not exist"
            )
        elif resolution.canonical_id == self_canonical:
            # Catches BOTH the literal self-reference and the alias that resolves BACK to the
            # entity itself -- which reads as a valid successor and is a closed loop.
            message = (
                f"{raw_id}: {field} -> {ref!r} resolves to the entity itself "
                f"({self_canonical}); an entity cannot be its own successor"
            )
        elif resolution.canonical_id not in live_hypotheses:
            # Resolvable is not enough. An ARCHIVED successor resolves perfectly well and is still
            # not a reason: the entity it points at is no longer part of the live corpus.
            message = (
                f"{raw_id}: {field} -> {ref!r} resolves to {resolution.canonical_id}, which is not "
                f"a live entity in this project; a closed entity's successor must be one that exists"
            )
        else:
            continue
        violations.append(
            ResolutionViolation(entity_id=raw_id, field=field, ref=ref, message=message)
        )

    return violations
```

> ### ⚠️ `ref not in known_ids` is the WRONG QUESTION — it fails in both directions
>
> Raw string membership against a set of canonical ids is not resolution, and rev 3's
> `known_ids: set[str]` was **wrong in both directions at once**:
>
> - **It rejects a valid alias.** `superseded_by: hypothesis:0009` — an alias, or a scoped
>   `evolution:hypothesis:0009`, or any spelling in `aliases:` / the manual alias map — resolves
>   perfectly under `ReferenceResolver` and is a **real, live successor**. Raw membership calls it
>   dangling and **blocks a correct corpus.**
> - **It misses an alias that resolves back to the entity itself.** The self-check was
>   `ref == entity_id`, a *string* comparison. An alias of `0009` written on `0009` is not equal to
>   `0009` as a string, resolves fine, and sails through as a valid successor — **a closed loop the
>   check exists to catch.**
>
> **Materialization already resolves these references** through `ReferenceResolver` (`materialize.py`
> builds it via `ReferenceResolver.from_entities(sources.entities, manual_aliases=…,
> identity_table=…)`). A validator that answers the question differently from the materializer is a
> **second authority for one fact** — precisely the collapse this arc exists to undo, and precisely
> the defect Task 6b's ownership check had one layer up. So: **resolve through the same semantics,
> then require the CANONICAL target to be in the live local set.**
>
> Resolution and liveness are **two questions, and both must be asked.** An *archived* successor
> resolves perfectly and is still not a reason — the entity it names is no longer in the live corpus.
>
> **Four cases, all four tested** (`test_resolution.py`), because each is a different failure:
>
> | case | resolves? | canonical target | verdict |
> |---|---|---|---|
> | **live alias** (`hypothesis:0009` → `hypothesis:0009-local-…`) | yes | live, ≠ self | **clean** — raw membership would have blocked it |
> | **self-alias** (an alias of the entity, written on the entity) | yes | **== self** | **violation** — raw `==` would have missed it |
> | **archived alias** | yes | not live | **violation** — resolvable ≠ a reason |
> | **unresolved token** (`hypothesis:9999-nope`) | no | — | **violation** |

- [x] **Step 3b: WIRE it — in the CHECK. The LOADER must not build a resolver.** *(SHIPPED — and it
  reverses this step's original instruction. Read the box.)*

> ### ☠️ THE LOADER MUST NOT BUILD A REFERENCE RESOLVER. This was tried TWICE and reverted twice.
>
> Every earlier revision of this step said: add a `resolution_violations` carrier to `ProjectSources`
> and populate it in a **second pass** inside `load_project_sources`, because the loader has the
> whole corpus, the manual aliases and the identity declarations right there. **It is wrong**, and
> the reason has nothing to do with lineage:
>
> ```
> ReferenceResolver.from_entities  ->  build_alias_map  ->  RAISES AliasCollisionError
>                                                           when two entities claim one alias
> ```
>
> So a resolver built inside the loader makes a corpus with a duplicated alias **UNLOADABLE** instead
> of **REPORTABLE** — for *every* caller of `load_project_sources`, including the many that never
> look at a hypothesis. **`annotation/proposition_archive.py` exists precisely to REPORT and unblock
> those collisions, and calls `load_project_sources` on a colliding corpus ON PURPOSE.** The
> loader-side pass breaks three of its tests.
>
> **Loading and resolving are different jobs.** The loader reads and projects sources. Resolution is
> analysis *over* an already-loaded corpus, and it belongs to the caller that wants an answer and can
> handle the collision. That is already the convention: **all seven** other
> `ReferenceResolver.from_entities` call sites build their own resolver, and `migrate.py:162` catches
> `AliasCollisionError` itself.
>
> There is **no `resolution_violations` carrier** and **no second pass**. `ProjectSources` is
> untouched by this task.

  **`validate/checks/hypotheses.py`** — the check builds the resolver and calls `check_resolution`.
  Rule `hypothesis.dangling-lineage`, severity **WARN** (ERROR arrives with Task 12's ratchet, per
  kind). Same three arguments as `materialize.py`, because a validator that resolves a reference
  differently from the materializer is a second authority for one fact.

```python
@Check(section="hypotheses...", order=6)
def check_dangling_lineage(ctx: ValidateContext) -> Iterator[Result]:
    sources = ctx.project_sources()
    resolver = ReferenceResolver.from_entities(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        identity_table=build_identity_table(sources),
    )
    path_by_id = {
        str(doc.frontmatter.get("id")): doc.path
        for doc in sources.markdown_documents
        if doc.frontmatter.get("id")
    }

    # ☠️ LIVE **HYPOTHESES** -- not every loaded entity. The schema constrains only the AUTHORED
    # spelling (`superseded_by` is `pattern: "^hypothesis:"`), and an ALIAS may point ANYWHERE: put
    # `aliases: [hypothesis:looks-valid]` on `dataset:0002` and the ref RESOLVES to a dataset, is
    # found in an all-entities set, and reports CLEAN -- a hypothesis superseded by a dataset.
    #
    # Keyed on `canonical_id`, NOT `id`: the resolver ANSWERS in canonical ids.
    #
    # `kind` alone also makes these LOCAL, by CONTRACT: commons can own only dataset/paper/topic/
    # theme (`_TYPE_DIR_TO_TYPE`, commons/adapter.py:25 -- the kind comes from the directory, and
    # there is no `hypotheses/` one), so a commons entity can never be a hypothesis. A locality
    # filter on top would be dead code; a test pins that contract so it fails loudly if it changes.
    live_hypotheses = {e.canonical_id for e in sources.entities if e.kind == "hypothesis"}

    for entity in sources.entities:
        for violation in check_resolution(
            entity.model_dump(mode="json"), targets=resolver, live_hypotheses=live_hypotheses
        ):
            path = path_by_id.get(violation.entity_id)
            yield Result(
                Severity.WARN, Path(path) if path else None, None,
                violation.message, "hypothesis.dangling-lineage", None,
            )
```

  **It reads the four fields Step 3 put on the model** — before those, `model_dump` yields a record
  with no lineage at all and this check reports clean forever. `ResolutionViolation`'s typed fields
  are why this is a projection and not a re-parse: a `list[str]` would have forced the check to
  recover `entity_id` and `field` out of an English sentence.

  **Two guards, and they prove different things** (`tests/test_loader_resolver_boundary.py`,
  `tests/test_resolution_wiring.py`):

  - **behavioural** — `test_the_LOADER_does_not_build_a_RESOLVER` loads a corpus whose two entities
    claim one alias and asserts `load_project_sources` does not raise.
  - **architectural** — an **AST guard** asserting `graph/sources.py` contains no `.from_entities()`
    call and no import of `reference_resolution`, at any scope. This is the one that matters: the
    behavioural test pins the *symptom*, and **a loader that builds the resolver, catches
    `AliasCollisionError`, and carries on would pass it** — reintroducing the coupling *and* adding a
    swallowed exception. Verified by mutation: under exactly that change the behavioural test passes
    and only the AST guard fails. The AST guard carries its own self-check
    (`test_the_GUARD_ITSELF_still_matches_a_real_construction`), because a guard that no longer
    recognises what it forbids is not a guard, it is a green light.


  *(The third call site — the **write boundary** — is **Task 10's**. Task 7a splits that boundary
  into a private `_prepare_write` / `_commit_write` pair and builds the derived writer
  `consolidation._prepare_supersession` on it; Task 10 puts schema validation + this resolution guard
  **inside `_prepare_write`**, so both entry points inherit them. Neither writer takes a
  `superseded_by` parameter: the field is **derived**, and a caller-supplied spelling of it — from a
  CLI flag or from Python — is exactly what rev 10 deleted.)*

- [x] **Step 3b-ii: Emit `sci:verdict`** — **without this, Step 3c's check is inert.**
  `materialize.py:646` emits `projectStatus` and `disposition` and **no verdict at all**, so the
  graph check below would read `None` for every hypothesis and find a disagreement **never**. One
  triple, beside the status:

```python
    knowledge.add((uri, SCI_NS.projectStatus, Literal(entity.status)))
    verdict = getattr(entity, "verdict", None)
    if verdict:
        knowledge.add((uri, SCI_NS.verdict, Literal(verdict)))
```

  **Additive only.** Deleting `sci:disposition` stays in **Task 10**, where `attention.py:125-137`
  (its only consumer) is rewired in the same commit — removing a predicate while a reader still
  queries it is the same class of gap in the other direction.

  Gate it in the artifact, not just the unit test: the graph diff must show **new `sci:verdict`
  triples on exactly the hypotheses that carry one, and no other triple changed.** Until Task 9
  migrates the corpus, zero hypotheses carry a verdict — **so the expected diff here is EMPTY**,
  and that is a real result only because the emission is proven by a fixture test that *does*
  carry one. A green from a corpus with nothing to emit proves nothing on its own.

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
> **Resolution — scope it explicitly, do not quietly claim it.** A qualifying basis is one of exactly
> two things, and **they do not have the same reach**:
> 1. an **admissible, polarity-agreeing evidence-line unit** on the hypothesis **or a core member**.
>    Both reaches are real: the `supports`/`disputes` `RelationKind`s declare `source_kinds`
>    including `evidence-line` and `target_kinds=["proposition", "hypothesis"]`
>    (`profiles/core.py:648-660`) — that admission is what makes a hypothesis a legal target.
> 2. a **`falsification`** record on a **CORE PROPOSITION MEMBER — and only there.** This is the
>    *"explicitly linked negative adjudication"* the `refuted` row calls for.
>
> ⚠️ **A falsification "on the hypothesis" CANNOT EXIST — do not look for one.** `FalsificationEntity`
> declares `falsifies: str` as **required**, and `_add_falsification_relations`
> (`materialize.py:1258`) **hard-raises** unless the
> target resolves to `kind == "proposition"`: *"falsification targets must be propositions"*
> (`materialize.py:1274`). An earlier draft of this clause said "on the hypothesis or a core member",
> which would have sent the implementer looking for a triple the materializer refuses to write — the
> **same defect as the interpretation clause above**, made twice in one paragraph.
>
> **Interpretations are OUT OF SCOPE until they reach the graph.** Either wire them (a separate
> slice: interpretation must become a graph kind with a typed edge to the hypothesis) or **amend
> design rev 8 point 2 to say evidence-line-and-falsification basis.** Do not ship a check whose
> docstring claims a basis it cannot read. *(File as a defect against rev 8.)*

- [x] **Step 3c-0: REGISTER the check — or it never runs, and every test still passes.**

  Writing `verdict_agreement.py` does **not** enable it. `validate` runs only what
  `CANONICAL_CHECK_MODULES` names (`checks/__init__.py:25`): `_load_canonical_checks` imports each
  listed module, and the `@Check` decorator appends to `CANONICAL_CHECKS` **as an import side
  effect**. A module nobody imports registers nothing.

  Add `"verdict_agreement"` to that tuple. **Do it in the same commit as the module** — the registry
  is eagerly loaded, so a name listed before its file exists is an immediate `ModuleNotFoundError`
  that breaks the entire package.

  > ### ☠️ Why the unit tests CANNOT catch this — and why AN END-TO-END TEST CANNOT EITHER
  >
  > `test_verdict_agreement.py` imports `verdict_agreement` to get at its helpers. **That import runs
  > the decorator.** So the check registers itself *inside the test process* and every unit test
  > passes — while `science validate` in a real project never calls it. The suite is green and the
  > feature is off. This is the silent-instrument failure verbatim, one layer up.
  >
  > **Rev 1 answered that with an end-to-end test through `run_validate`, and that answer is WRONG.**
  > Established by mutation, not by argument — unregister the module and run:
  >
  > ```
  > pytest tests/test_check_registry_is_complete.py                      -> BOTH tests fail
  > pytest tests/test_verdict_agreement.py tests/test_check_registry...  -> only the FIRST fails
  > ```
  >
  > The decorator fires on **import**, and the import happens in the *same pytest process*. So by the
  > time the e2e test calls `runner.run`, the check is registered **no matter what the tuple says**.
  > In the full suite — which always contains both files — an e2e test can **never** catch an
  > unregistration. It is order-dependent, and its green reads as coverage it does not have. *The
  > proposed guard had the same defect as the thing it was guarding against.*
  >
  > The registry fails **loud** in one direction (listed-but-missing → `ModuleNotFoundError`) and
  > **silent** in the other (present-but-unlisted → never runs). Only the silent direction needs a
  > guard, and **only a test that reads no registry state can be it**: compare the DIRECTORY to the
  > TUPLE. Derived from the filesystem, not hand-listed — a guard that enumerates its own scope has a
  > hole by construction, which is the very hole it would be closing.
  >
  > The e2e test still ships, renamed to what it actually proves: a **wiring** test (a registered
  > check, through the real entry point, over a real materialized graph, reaches a hypothesis and
  > emits its rule). That is worth having. It is simply not the thing that catches an unlisted module.

```python
# science/tests/test_check_registry_is_complete.py
from pathlib import Path


def test_EVERY_check_module_on_disk_is_REGISTERED() -> None:
    # THE GUARD. Immune to import order BY CONSTRUCTION: disk vs. tuple, no registry state read.
    # A check module that exists but is not named in CANONICAL_CHECK_MODULES is dead code that looks
    # exactly like a working check -- it has a @Check decorator, it has passing unit tests, and
    # `validate` never calls it.
    from science_tool.validate import checks

    on_disk = {
        path.stem
        for path in Path(checks.__file__).parent.glob("*.py")
        if path.stem != "__init__"
    }
    assert on_disk == set(checks.CANONICAL_CHECK_MODULES), (
        f"unregistered: {sorted(on_disk - set(checks.CANONICAL_CHECK_MODULES))}; "
        f"listed but absent: {sorted(set(checks.CANONICAL_CHECK_MODULES) - on_disk)}"
    )


def test_a_registered_check_REACHES_a_real_project(tmp_path) -> None:
    # WIRING, not registration (see the box above): `runner.run` -> the graph -> the check -> a rule
    # on a real hypothesis. It proves the check is reachable from the real entry point and fires on
    # real materialized input, rather than only when a test hands it a hand-built context.
    #
    # The check reads `knowledge/graph.trig`; writing source alone leaves `_load_belief_graphs`
    # returning `(None, None)` and the registered check correctly emitting NOTHING. Build the
    # artifact first, or this test goes green without ever exercising the verdict surface.
    from science_tool.graph.materialize import materialize_graph

    write_hypothesis(tmp_path, "0001-x", status="complete",
                     extra={"verdict": "supported"})          # no basis -> missing-basis
    assert materialize_graph(tmp_path).is_file()              # prove the check has something to read

    rules = {r.rule for r in runner.run(tmp_path, strict=False, verbose=False).results}
    assert "verdict.missing-basis" in rules
```

- [x] **Step 3c: The verdict-agreement GRAPH check** (design rev 8, contract point 2 — *as amended*)

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

SCOPE -- stated, not assumed, because a basis this check cannot READ is a basis it must not CLAIM.
A qualifying basis is exactly one of two things, and their REACH DIFFERS:

  * an admissible, polarity-agreeing EVIDENCE-LINE unit -- on the hypothesis OR one of its CORE
    members. A hypothesis is a LEGAL evidence target: the `supports`/`disputes` relation kinds
    declare target_kinds ["proposition", "hypothesis"] from an evidence-line source
    (profiles/core.py:648-660);
  * a FALSIFICATION record -- on a CORE PROPOSITION MEMBER, and ONLY there.

A falsification ON THE HYPOTHESIS cannot exist and is not looked for: `FalsificationEntity.falsifies`
is required, and materialization hard-raises unless it resolves to a proposition ("falsification
targets must be propositions", materialize.py:1274).

INTERPRETATIONS are out of scope: `interpretation` is not a graph kind (no such entity in the
registry, no typed edge to a hypothesis), so rev 8's "or interpretation basis" clause cannot be
enforced here. Do not imply otherwise in a message.
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

        # The REAL config path -- `scalar_enabled` is not a knob this check invents. It reads an
        # ACTIVE decision in `core/decisions.md` (`belief_scalar.py:184`), and `belief_profile.py:294`
        # resolves it exactly this way. An earlier draft wrote `scalar_enabled=...` -- a literal
        # ellipsis, which is a `TypeError` at the first hypothesis and a lie in a code review.
        composed = belief_for_entity(
            knowledge, provenance, hyp_uri,
            scalar_enabled=belief_scalar_enabled(ctx.project_root),
        )

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
                # The message must name the basis the check ACTUALLY LOOKS FOR. An earlier draft
                # offered "or falsification on the hypothesis" -- a record that CANNOT EXIST
                # (materialize.py:1274) -- so the finding told the author to write something the
                # materializer would refuse. The two reaches differ, and the message says so.
                f"{hyp_uri}: verdict {verdict!r} has no qualifying basis (no admissible, "
                f"polarity-agreeing evidence line on the hypothesis or a core member, and no "
                f"falsification on a core proposition member). "
                f"A verdict is an adjudication OF something.",
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
| `supported` | **nothing composes** — the composed magnitude is `speculative` — **or** an unresolved decisive refutation stands. *(Not "the magnitude is below the `supported` rung" — see the ruling below. The ERROR case is emitted separately, and both may fire.)* |
| `partially-supported` | **either limb is missing.** It is a **conjunction** — *some support* **plus** *some unresolved/disputed/unsupported portion* — so it disagrees when there is **no admitted support unit** in scope, **or** when there is no unresolved/contested/refuted/falsified portion. *(This row said only the second half in earlier drafts. See ruling 4: the first half is what stops a wholly-disputed hypothesis from reading as `partially-supported` in silence.)* |
| `weakened` | **no** disputing evidence and no negative adjudication basis. **Never infer a historical trajectory from one snapshot** — a true weakening claim needs a prior `belief_snapshot`; absent one, only report the *absence of any dispute*, never the absence of *change*. |
| `refuted` | no decisive refutation and no linked falsification. **No single-source ceiling** — one decisive independent test is a legitimate refutation. |

> ### ⚠️ FIVE RULINGS the snippets above did not survive contact with — found while implementing
>
> *(Rulings 4 and 5 came from a REVIEW of the shipped check, not from writing it — the first three
> were caught at the keyboard, these two only under someone else's execution. Both were live defects
> in `57b36c39`, and neither was caught by its 22 tests. Recorded here because the plan's own table
> row is what encoded the first of them.)*
>
> **1. `supported` may NOT be tested against the `supported` RUNG — that is the single-source ceiling
> coming back through the side door.** The table's *"the composed belief does not support it"* reads
> naturally as `magnitude < BeliefMagnitude.SUPPORTED`. It cannot be: `_base_magnitude` returns
> **`fragile`** for a lone support unit (`well_supported` needs ≥2 clean units; one unit is fragile by
> the corroboration rule, belief.py:310-313). So the rung test would warn on **every verdict backed by
> a single decisive experiment** — the exact inversion this design named when it killed
> `belief.single-source-ceiling`, and it would have fired on the plan's OWN control test
> (`test_an_ADMISSIBLE_unit_IS_a_basis`, which expects silence). The honest complaint is that
> **nothing composes at all**, or that **a refutation stands**. Both are emitted; neither is a ceiling.
>
> **2. `capped_by_refutation` is NOT the refutation predicate.** It is the flag for *"a decisive
> refutation pulled the magnitude DOWN"* (belief.py:365-368) — so a claim with a decisive refutation
> and **no support** composes to `speculative`, is never capped, and the flag reads **False**. That is
> *precisely* the `supported`-over-a-bare-refutation case `verdict.refutation-masked` exists to catch,
> and a check built on the flag would have been silent on it. Ask the real question instead: is there
> an **admitted decisive refuting unit**? `dispute_units` is the reduced, admitted, non-diagnostic
> list — the same one `aggregate_belief` itself tests. *(Mutation-proven: swapping in the flag fails
> 4 tests, including both refutation tests.)*
>
> **3. `_unit(stance="refutes")` names a stance that does not exist.** `collect_evidence_units` reads
> exactly two predicates, `cito:supports` and `cito:disputes` (belief.py:143). A refuting edge **is**
> a `disputes` edge that additionally satisfies `is_decisive_refutation` (independent + strong +
> direct_test + whole_claim). The shipped fixture makes `disputes` decisive by default, so the
> polarity control tests polarity and nothing else.
>
> **4. `partially-supported` is a CONJUNCTION, and the disagreement table wrote it as a
> disjunction.** The contract at line ~3370 is explicit — *"some support **plus** unresolved /
> disputed / unsupported portions"* — but the `_disagreement` row asked only for the **second** limb.
> With no support anywhere in scope, **every portion is unsettled by definition**, so the shipped
> `_has_partial_aspect` returned `True` for three corpora that have no support at all: **no evidence
> whatsoever**, **only a decisive dispute**, and **only a falsification**. All three passed in
> silence, and the dispute-only and falsification-only cases emitted **nothing at all** — `disputes`
> and a linked falsification are both *qualifying bases* for `partially-supported`, so
> `missing-basis` stayed quiet too, and `disagrees-with-computed` was the only thing standing between
> a wholly-refuted hypothesis and a green run. It was not standing. Agreement now requires **both**:
> ≥1 admitted **support** unit **and** ≥1 unresolved/contested/refuted/falsified portion.
>
> ☠️ **The old positive control CODIFIED the defect.** `test_partially_supported_with_a_refuted_CORE_
> member_is_NOT_a_disagreement` had a *sole* core member, refuted, with **no supported portion** — a
> corpus that is not partially supported at all. It is green under a check that never reads the
> support limb, and it was. The control now carries **two** core members: one supported, one refuted.
> *(Mutation-proven: restoring the disjunction fails exactly the three new regressions.)*
>
> **5. The `supported` disagreement message made a FALSE CLAIM.** `_disagreement` reported *"no
> admissible evidence composes to any support at all"* on **any** speculative composition. But
> `belief_for_entity` is **weakest-link over core members**: an admissible supporting line **directly
> on the hypothesis** coexists with a speculative composition the moment one core member has no
> support of its own. The message told the author to write evidence they **had already written**. A
> check may not name a fact it did not read — `_speculative_reason` now names the actual locus (which
> core member is holding the conjunction down), and keeps the flat message only for the case where it
> is true. *(Mutation-proven, with a control asserting the flat message is still reachable.)*
>
> **And one GAP: the plan's test list never exercised the falsification limb.** The basis contract has
> two limbs, and only the evidence-line one had tests — the `falsification`-on-a-core-member limb, the
> *"explicitly linked negative adjudication"* the `refuted` row depends on, was specified in prose and
> gated by nothing. Two tests ship for it, with a polarity control proving it cannot ground
> `supported`.

- [x] **Step 3c-i: The verdict subsystem's FAILING TESTS — written BEFORE 3b-ii and 3c, not after.**

> **The whole subsystem had no Step-1 tests.** Every claim in the two tables above — polarity,
> admissibility, core-member scope, the non-ordinal matrix, the two rules firing independently —
> was asserted in **prose** and gated by **nothing**. And the artifact diff cannot stand in for
> them: **no corpus hypothesis carries a verdict until Task 9**, so that diff is *empty by
> construction* and would go green over a `check_verdict_agreement` that returned `[]` on every
> input. *A test suite that cannot distinguish a working check from a check that does nothing is
> not a suite.* These are fixture-built graphs, so they run today.

```python
# science/tests/test_verdict_agreement.py

def test_a_verdict_REACHES_the_graph(tmp_project) -> None:
    # Step 3b-ii's gate. Without the triple, every test below passes vacuously -- the check reads
    # `None`, `continue`s, and yields nothing, forever.
    write_hypothesis(tmp_project, "0001-x", status="complete", extra={"verdict": "supported"})
    knowledge = _knowledge_graph(materialize_graph(tmp_project))

    assert str(next(knowledge.objects(_uri("hypothesis:0001-x"), SCI_NS.verdict))) == "supported"


def test_an_ABSENT_verdict_is_not_a_finding(tmp_project) -> None:
    # Absence == "not yet assessed" (D1). The common case, and it must be silent.
    assert _verdict_results(_graph(verdict=None, basis=None)) == []


# ---- a basis is not merely an EDGE: three ways to have one and still have nothing ----

# > **NO SUPPRESSION — and that is why these expect TWO rules, not one.**
# >
# > Rev 1 asserted `== ["verdict.missing-basis"]` on all three. That is not what a correct
# > implementation emits. Evidence that fails polarity, admissibility, or scope fails it for
# > `_qualifying_basis` AND for the composition -- so the verdict has no basis *and* disagrees with
# > the belief the corpus actually composes to. **Both are true, and the matrix above says both
# > must be said.** Exact-equality on one rule rejects the implementation this plan specifies.
# >
# > The alternative -- suppress `disagrees-with-computed` whenever `missing-basis` fires -- is
# > **rejected.** It is precisely the masking forbidden two tests below, where the same collapse is
# > called out for `missing-basis`/`refutation-masked`: the rules carry different severities and
# > different gate tiers, so folding them silently re-grades whichever one loses. A third authority
# > deciding which true finding an author is allowed to see is the collapse this arc exists to undo.
# >
# > So each test below asserts the **whole rule set**, and each is paired with a **matched control**
# > differing in exactly the property under test. Without the control, a check that always yielded
# > both rules would pass every one of them.

def test_an_edge_of_the_WRONG_POLARITY_is_not_a_basis() -> None:
    # A `supports` line is not a basis for `refuted`. `if not units` -- the drafted body -- passes.
    # `disagrees-with-computed` also fires (matrix, `refuted` row: no decisive refutation and no
    # linked falsification -- a lone `supports` unit is neither).
    results = _verdict_results(_graph(verdict="refuted", basis=_unit(stance="supports")))
    assert {r.rule for r in results} == {
        "verdict.missing-basis", "verdict.disagrees-with-computed",
    }


def test_a_REFUTING_edge_IS_a_basis_for_refuted() -> None:
    # The POLARITY control: identical but for the stance. Silence here is what proves the test
    # above is about polarity and not about `refuted` being unsatisfiable.
    assert _verdict_results(_graph(verdict="refuted", basis=_unit(stance="refutes"))) == []


def test_an_INADMISSIBLE_unit_is_not_a_basis() -> None:
    # Excluded by the belief policy => it does not compose => it cannot adjudicate. And because it
    # does not compose, the composed belief does not support `supported` either.
    results = _verdict_results(_graph(verdict="supported", basis=_unit(admissible=False)))
    assert {r.rule for r in results} == {
        "verdict.missing-basis", "verdict.disagrees-with-computed",
    }


def test_an_ADMISSIBLE_unit_IS_a_basis() -> None:
    # The ADMISSIBILITY control: same unit, same polarity, same scope -- admitted by the policy.
    assert _verdict_results(_graph(verdict="supported", basis=_unit(admissible=True))) == []


def test_evidence_on_a_RIVAL_member_is_not_a_basis() -> None:
    # Scope: the hypothesis or its CORE members. A rival/background member adjudicates nothing
    # about THIS hypothesis -- and `belief_for_entity` already excludes them from the conjunction
    # (`MembershipRole`, bundle_belief.py), so a check that counted them would contradict the
    # composition it claims to read. It is excluded from the composition too, hence both rules.
    results = _verdict_results(
        _graph(verdict="supported", basis=_unit(on_member="rival"))
    )
    assert {r.rule for r in results} == {
        "verdict.missing-basis", "verdict.disagrees-with-computed",
    }


def test_evidence_on_a_CORE_member_IS_a_basis() -> None:
    # The SCOPE control. Without it the tests above pass for a payload that has no basis at all.
    assert _verdict_results(_graph(verdict="supported", basis=_unit(on_member="core"))) == []


# ---- the two rules are INDEPENDENT: one may not mask the other ----

def test_the_three_rules_fire_INDEPENDENTLY() -> None:
    # A `supported` verdict, no qualifying basis, AND an unresolved decisive refutation.
    #
    # ALL THREE fire, and this is the strictest statement of the no-suppression rule in the suite.
    # The emitter has no `continue` between the rules, so each is evaluated on its own facts:
    #   - no qualifying basis at all                       -> missing-basis        (WARN)
    #   - `supported` over a decisive refutation           -> refutation-masked    (ERROR)
    #   - and the composed belief plainly is not `supported` -> disagrees-with-computed (WARN)
    #
    # An earlier draft expected only the first two. That is not what the specified emitter produces,
    # and it contradicts this suite's own adjacent tests: `test_an_INADMISSIBLE_unit_is_not_a_basis`
    # already expects `disagrees-with-computed` for a `supported` verdict whose evidence does not
    # compose. Here NOTHING composes AND a decisive refutation stands -- so it disagrees at least as
    # hard. Expecting two rules would reject a correct implementation, and the only way to make the
    # two-rule oracle true is to SUPPRESS the third -- the masking this box forbids.
    results = _verdict_results(
        _graph(verdict="supported", basis=None, refutation=_decisive())
    )

    assert {r.rule for r in results} == {
        "verdict.missing-basis",
        "verdict.refutation-masked",
        "verdict.disagrees-with-computed",
    }
    assert {r.rule: r.severity for r in results} == {
        "verdict.missing-basis": Severity.WARN,           # >=11 of 15 cannot satisfy it -- never ERROR
        "verdict.refutation-masked": Severity.ERROR,      # the one hard invariant
        "verdict.disagrees-with-computed": Severity.WARN, # explanatory, never a ceiling
    }


def test_a_refutation_DIRECTLY_on_the_hypothesis_is_caught_despite_bundle_members() -> None:
    # THE trap named in the box above: with core members, `belief_for_entity` takes the bundle
    # branch and NEVER calls `collect_evidence_units([uri])` -- so a decisive refutation attached
    # to the hypothesis ITSELF is invisible to the composition. Bundle dispatch would hide the very
    # thing `refutation-masked` exists to catch, and the suite would be green.
    results = _verdict_results(
        _graph(verdict="supported", members=["core"], refutation=_decisive(on="hypothesis"))
    )
    assert "verdict.refutation-masked" in {r.rule for r in results}


# ---- the matrix is NOT a ladder ----

def test_partially_supported_with_a_refuted_CORE_member_is_NOT_a_disagreement() -> None:
    # On an ordinal reading this is a contradiction. It is not: a decisively refuted constituent
    # is exactly what `partially-supported` asserts. Ordinalizing the verdict produces this
    # false positive, which is why the check reports a MATRIX and never compares rungs.
    results = _verdict_results(
        _graph(verdict="partially-supported", members=["core"], refutation=_decisive())
    )
    assert "verdict.disagrees-with-computed" not in {r.rule for r in results}


def test_partially_supported_with_NOTHING_partial_IS_a_disagreement() -> None:
    # The other side, or the test above is satisfied by a check that never fires at all.
    results = _verdict_results(
        _graph(verdict="partially-supported", basis=_unit(), members=[], refutation=None)
    )
    assert "verdict.disagrees-with-computed" in {r.rule for r in results}


def test_refuted_from_ONE_decisive_test_is_NOT_ceilinged() -> None:
    # A single-source ceiling applied to `refuted` would flag the STRONGEST POSSIBLE refutation as
    # unfounded. This is the shipped rule `belief.single-source-ceiling` NOT coming back.
    results = _verdict_results(
        _graph(verdict="refuted", basis=_unit(stance="disputes", sources=1), refutation=_decisive())
    )
    assert results == []


def test_weakened_is_never_inferred_from_ONE_snapshot() -> None:
    # `weakened` asserts a CHANGE. With no prior `belief_snapshot` there is no trajectory to read,
    # so the check may report only "no dispute exists" -- never "no weakening occurred".
    results = _verdict_results(_graph(verdict="weakened", basis=_unit(stance="disputes")))
    assert results == []
```

- [x] **Step 3d: Re-gate the hard invariant — and ONLY it.** Add **`verdict.refutation-masked`** to
  the `hygiene` tier in `validate/gates.py`; it inherits the gated ERROR that
  `belief.refutation-masked` held before Task 2b removed it.

  **`verdict.missing-basis` is WARN and ungated** (ruled 2026-07-13 — Task 3b). Not "ERROR, ungated
  for one release": at least 11 of the 15 migrating verdicts **cannot satisfy it**, so an ERROR would
  be an uncertified instrument failing real builds — the original incident, verbatim.

  **`verdict.disagrees-with-computed` is never gated** — a disagreement is information, not a fault.

  Assert what **exists at this task**, using the API that exists: `cumulative_rules(tier)`
  (`gates.py:50`). `severity_for_kind` is **Task 12's**, and `severity_of_rule` / `gates.TIERS` are
  nobody's — they do not exist anywhere. An earlier draft of this step called all three, so the
  regression it "added" could not have run. *A test written against an API that does not exist is
  not a weaker gate; it is not a gate.*

```python
def test_missing_basis_is_WARN_and_UNGATED() -> None:
    # >= 11 of the 15 migrating verdicts CANNOT satisfy this rule. An ERROR here would be an
    # uncertified instrument failing real builds -- the original incident, verbatim.
    #
    # FILTER for the rule under test. `supported` + no basis emits `disagrees-with-computed` too
    # (nothing composes, so the composed belief is not `supported`) -- so asserting over the WHOLE
    # result list tests the OTHER rule's existence as a side effect and fails on a correct emitter.
    # Assert the severity of the rule this test is named after, and nothing else.
    results = run_verdict_checks(graph_with(verdict="supported", basis=None))

    missing = [r for r in results if r.rule == "verdict.missing-basis"]
    assert [r.severity for r in missing] == [Severity.WARN]
    assert "verdict.missing-basis" not in cumulative_rules("hygiene")


def test_refutation_masked_IS_gated_at_hygiene() -> None:
    # The one hard invariant, inheriting the ERROR `belief.refutation-masked` held before Task 2b.
    assert "verdict.refutation-masked" in cumulative_rules("hygiene")
```

> **The kind/rule independence regression moves to Task 12**, which is where `_severity` and
> `_CERTIFIED_KINDS` are born. The claim it makes — *`hypothesis` being certified as a KIND says
> nothing about whether the corpus carries verdict bases, so `verdict.missing-basis` must stay WARN
> even then* — cannot be stated before the thing it constrains exists.

- [x] **Step 4: Green** — unit + wiring, **both suites whole**, plus `ruff` and `pyright`. Task 7
  now touches `science_model.entities` (Step 3) and `science_tool.graph.materialize` (Step 3b-ii),
  so neither suite is optional.

```bash
cd science/model && uv run --frozen pytest
cd science       && uv run --frozen pytest
cd science       && uv run ruff check && uv run pyright
```

- [x] **Step 4b: Prove the emission in the ARTIFACT — RUN 2026-07-13.** Rebuild `multiple-myeloma`
  through this worktree (`uv run --project "$WT" science graph build --local-only`, `cp`, restore —
  the Task 6 Step 4b procedure verbatim) and diff against the saved "before" graph.

> ### RESULT: the emission is INERT on the corpus, as predicted — and "byte-identical" was the wrong gate
>
> **`sci:verdict` triples in the rebuilt graph: ZERO.** Correct, and expected: no mm30 hypothesis
> carries a `verdict` until Task 9 migrates them. The emission is additive and changed no semantic
> triple.
>
> **But the diff is NOT byte-identical, and the cause is not this task.** Exactly **4 lines** differ,
> in exactly **two fields**, and both are *build provenance*:
>
> | field | why it differs |
> |---|---|
> | `schema:dateModified` | the build timestamp. Changes on **any** rebuild. |
> | `schema:text` (the source hash-inventory blob) | 3189 files, identical file set; **2 files' `sha256` differ** — `AGENTS.md` and `science.yaml`. |
>
> Those two files were edited by mm30 commit `fee79a07`, which landed **after** the last commit that
> rebuilt `knowledge/graph.trig` (`17976d17`). **The committed artifact is simply stale with respect
> to the committed source**, and any rebuild — with or without this change — surfaces that. mm30's
> working tree was clean before and after; the graph was restored.
>
> So the gate is corrected to what it can actually assert: **no semantic triple changes, and zero
> `sci:verdict` triples appear.** Demanding byte-identity of an artifact that carries a build
> timestamp and a source-mtime inventory asks for a green that cannot be produced — and a gate that
> cannot go green teaches the next person to skip it.
>
> The plan's own caveat stands and is why this is worth anything at all: a diff over a corpus with
> nothing to emit **cannot distinguish "additive and correct" from "does nothing at all."** The
> fixture test `test_a_verdict_REACHES_the_graph` is what proves the triple *is* emitted when a
> verdict exists, and dropping the emission fails **10** tests.

- [x] **Step 5: Commit.** — `57b36c39` (the check, its registration, the gate, and 22 tests).
  **Task 7 is COMPLETE.**

---

### Task 7a: The D4 supersedable gate — **compute** it, and land three of its four legs — **DONE 2026-07-14** (`b97ec0ea`, + `cda554c6` self-edge/duplicate-edge admission, + `677669b0` the `validate` relation-validity rules, + the shared relation stream and the cycle rule, + **`RULING 10`: the hand-written ladder DELETED**)

> ### ☠️ SIX REVIEW ROUNDS, SIX DEFECTS, ONE ROOT CAUSE — and the root cause is now GONE
>
> Every defect found in this task after it "shipped" — the self-edge, the duplicate edge, the silent
> `validate`, the unread `relations.yaml` carrier, the cycle filed as a branch, the archived subject
> that `--apply` stamped into a live record — is the **same mistake**: *this authority asked a
> narrower question than `materialize` asks.* Not a different question. A **narrower** one. Each fix
> closed one gap and left the frame intact, and the next review found the next gap in the same frame.
>
> **The frame was the defect, and patching it six times was the error.** `mark_superseded` and
> `check_supersession` re-derived, from a subset of the sources, a judgment `materialize` already
> makes from all of them.
>
> **RULING 10 deletes the re-derivation.** `graph/relation_audit.py` asks the graph builder itself —
> `admit_authored_relation`, extracted from `_add_authored_relation` — over the whole
> `sources.relations` stream, and collects the refusals instead of raising on the first. The
> hand-written admission ladder in `consolidation.py` (167 lines, four outcome buckets) is **gone**.
> Two rules nobody ever wrote now fire for free — a bare `sci:amends` self-edge, and an unsupported
> `graph_layer` — and the seam this box used to say was "bigger than Task 7a" is closed.
>
> **A rule the builder gains, the audit gains. A rule the builder loses, the audit loses. There is no
> third place to forget one.**

> ### ⚠️ TWO RULINGS on the SHIPPED builder — both found by REVIEW of `b97ec0ea`, not by writing it
>
> *Same pattern as Task 7's rulings 4 and 5: the defects that survive are the ones the author's own
> execution cannot see. Both were live in `b97ec0ea`; neither was caught by its 25 tests. Both are
> the **same root cause** — the builder asked what the relation model asks, but not everything
> `materialize` asks — and the fix for both is one sentence: **admission must ask exactly the
> questions the graph builder asks, on the CANONICAL pair.***
>
> **6. A self-supersession disappears completely — it does not even become a defect.** `materialize`
> raises `self-referential authored relation` whenever a resolved object equals its resolved subject,
> for **any** predicate, and it checks that **before** the kind pair. The builder checked only the
> kind pair — and a self-edge's pair is `K -> K`, **legal for every kind that supersedes its own
> kind**, which is every kind in the roster. So the edge was ADMITTED, and then `len(comp) < 2` threw
> away its one-node component *before classification ever ran*. No mismatch, no non-linear component,
> no blocker: **`--apply` returned clean over a corpus that does not build a graph.** It now BLOCKS,
> and the check runs on the canonical pair — so an alias that resolves back to its own source is
> caught too, which a comparison on the authored strings would miss.
>
> **7. Two spellings of one edge fabricate a branch, and the branch suppresses a valid chain.** An RDF
> graph is a **set** of triples: the identical triple authored twice is one edge, and `materialize`
> collapses it. The builder accumulated admitted edges in a **list** and counted degrees off it, so a
> duplicate — the same target twice, or the canonical id once and an alias of it once — became a
> second in-edge *and* a second out-edge. The component classified as **"branched or cyclic"** and was
> silently skipped. The corpus was valid; the tool refused to act on it; and the defect it reported
> **did not exist**. Edges are now a set, deduplicated on the canonical pair. *(The control that keeps
> this honest: two genuinely different targets must STILL be non-linear — mutation-proven, since
> "dedupe by superseder" would pass every duplicate test and quietly collapse real branches.)*

> **D5 shipped a `superseded` terminal for a kind that cannot be superseded.** The design states a
> bidirectional gate (§D4) and D5 implemented **none** of it:
>
> ```
> supersedable ⇔ schema admits `superseded`
>              ⇔ the lineage RelationKind admits the kind as an endpoint
>              ⇔ the supersession operation handles the kind
> ```
>
> All three legs are broken for `hypothesis`, and each one alone is enough to make the terminal a
> dead letter:
>
> | leg | state today | consequence |
> |---|---|---|
> | **schema** | `mixin-hypothesis-1.0` does not admit `relations:`, and `unevaluatedProperties: false` is ON | the **canonical** supersession edge cannot be authored on a hypothesis **at all** |
> | **relation** | `sci:supersedes` (`core.py:687-701`) admits only `interpretation`/`finding`/`discussion`/`report` (+3 status-less kinds) | authoring it anyway raises **`ValueError` in `materialize`** |
> | **operation** | `mark_superseded` writes `edit_entity(..., status="superseded")` — **status and nothing else** (`consolidation.py:238`) | Task 10's schema boundary **rejects the tool's own write**: no lineage, no `closure_basis` |
>
> **The corpus proves the triangle has never been exercised.** Across the **certified roster** —
> **18 roots / 147 hypotheses**, derived by `field_inventory` (Task 11 Step 0), *not* by a hand
> grep: **0 superseded, 0 archived, 0 authoring `relations:`, and 0 authoring `superseded_by`,
> `resynthesized_into`, `supersedes`, `closure_basis`, or `archive_ref`.** Not one. Three broken
> legs stayed silent because nobody has ever superseded a hypothesis — *they couldn't.* **Nothing
> to migrate, and therefore no excuse to get it wrong.**
>
> > **An earlier draft of this box said 150, from an ad-hoc `grep -rl '^kind: hypothesis' ~/d`.**
> > That sweep double-counted this worktree's own `meta/` copy and keyed on a `kind:` line many
> > hypotheses do not author. The zero-use conclusion survived re-derivation; **the number did
> > not.** The roster is *derived* precisely so that no claim rests on a number nobody can
> > reproduce — and the first thing that number was used for was an argument. *Certify the
> > population against the disk, then argue from it.*
>
> **And the design understated its own gate by a factor of four.** It named `topic`/`decision`/
> `theme`. Executed against `CORE_PROFILE`, the gate names **twelve** half-wired kinds: `decision`,
> `inquiry`, `mechanism`, `method`, `observation`, `plan`, `pre-registration`, `proposition`,
> `synthesis`, `theme`, `topic`, `workflow-step`. **A gate stated in prose is not a gate** — this
> one is derived from `CORE_PROFILE` and executed, which is the only reason we know the number.

**Files:**
- Modify: `science/model/src/science_model/schemas/mixin-hypothesis-1.0.json` (admit `relations:`)
- Modify: `science/model/src/science_model/profiles/core.py:687` (`supersedes` endpoints)
- Modify: `science/src/science_tool/entities.py:935` — **split `edit_entity` into
  a PRIVATE `_prepare_write` (find + merge + render + validate; writes nothing) and a PRIVATE
  `_commit_write` (atomic replace)**. `edit_entity` becomes prepare-then-commit and is
  otherwise unchanged. **It gains no `superseded_by` parameter** — that field is derived, and
  putting it on the authored-edit surface would re-mint the second spelling rev 10 deleted.
- Modify: `science/src/science_tool/consolidation.py:195-240` — the graph canonicalizes before it
  classifies, and carries every edge-admission outcome plus both inverses; `_prepare_supersession` is
  the derived writer and it is **module-private**; the kind-pair refusal; the idempotent
  reconciliation.
- Create: `science/src/science_tool/validate/checks/supersession.py` — `<kind>.unbacked-inverse`,
  **WARN** (ERROR at Task 12's ratchet, which lists this file). Kind-scoped rule names, because the
  gate keys on rule name alone. It *consumes* `SupersedesGraph` rather than re-deriving edges: one
  authority, several readers.
- Modify: `science/src/science_tool/validate/checks/__init__.py:25-76` — add `"supersession"` to
  `CANONICAL_CHECK_MODULES`. **This is not bookkeeping; it is half the check.** `@Check` only runs when
  the module is imported, and `_load_canonical_checks` importing this tuple is the only importer.
  Decorated-but-unlisted = never registered = never run.
- Test: `science/model/tests/test_supersedable_gate.py`, `science/model/tests/test_mixin_hypothesis.py`,
  `science/tests/test_entity_commands.py`, `science/tests/test_consolidation_mark_superseded.py`,
  `science/tests/validate/test_check_supersession.py`
- **Snapshot:** `science/tests/validate/snapshots/text_default.txt` — the check count moves. Regenerate
  it in the same commit; a stale snapshot has already been left red on main once (`5c2b44f1`).

**Interfaces:**
- Consumes: `PROFILE`, `V.validate_as` (Task 6); `relation_allows_kinds` (`relations.py:19`);
  `load_archive_index` **and `ArchiveIndex.resolvable_ids()`** (`archive.py:51`);
  `load_project_sources` + `ReferenceResolver.from_entities(..., identity_table=build_identity_table(sources))`
  — the SAME CALL `materialize` makes (`materialize.py:349`), not a reimplementation of it
- Produces: `_prepare_write(project_root, ref, fields) -> _PreparedWrite` and
  `_commit_write(prepared) -> EntityWriteResult` — **both private, and so is `_PreparedWrite`**, which
  carries a module-private HMAC its `__post_init__` verifies and `_commit_write` **re-verifies at the
  write boundary**, so the commit half rejects both a mutated token and a duck-typed substitute
  (privacy by underscore and a Python type annotation are conventions; the runtime MAC check is the
  enforcement);
  `IdResolution` — `.canonical(raw)`, `.mutable`, `.archived` (the WRITER's populations, and only
  those: `.kind_of()` is **gone** with the ladder — legality is not this module's question);
  `graph.relation_audit.audit_relations(project_root, sources) -> RelationAudit`, with
  `.admitted: tuple[AdmittedRelation, ...]`, `.defects: tuple[RelationDefect, ...]` and
  `.relations(name)` (**by profile relation NAME, never by CURIE string-compare** — a predicate has
  more than one legal spelling);
  `SupersedesGraph.path_by_id` (the check reports a *file*: `Result` has no `entity_id` field);
  `SupersessionError`; `report["invalid_relations"]` (`{code, path, subject, predicate, object,
  message}` — **one key, the audit's verdict**, replacing the four hand-maintained buckets),
  `report["archived_targets"]`, `report["unmanaged_targets"]`, `report["unbacked_inverses"]`,
  `report["to_repair"]`, `report["repaired"]`
- Produces: a **registered** `validate` check — `checks/supersession.py` decorated with `@Check`, and
  `"supersession"` in `CANONICAL_CHECK_MODULES`. Both, or it never runs.
- **Does NOT produce a public `stamp_supersession`, and does NOT produce a public prepare.** The
  derived writer is `consolidation._prepare_supersession(project_root, graph, member)` — it takes the
  **graph**, not a lineage string, so the superseder is read from `graph.superseder_by_id` (i.e. from
  an admitted canonical edge) and **there is no argument a caller could corrupt.** `edit_entity` stays
  explicit and keyword-only: **no `superseded_by`, and no `**kwargs` to smuggle it through.** See the
  box below.

```python
# consolidation.py -- the relation kind, resolved ONCE from the profile. Used by the edge-admission
# filter above; an earlier draft referenced `_SUPERSEDES_KIND` without ever defining it.
from science_model.profiles.core import CORE_PROFILE
from science_model.relations import relation_allows_kinds


def _supersedes_kind() -> RelationKind:
    return next(r for r in CORE_PROFILE.relation_kinds if r.name == "supersedes")


class SupersessionError(RuntimeError):
    """An authored `sci:supersedes` edge that is not admissible as an edge -- the relation model
    forbids the kind pair, or the target resolves nowhere. Apply is all-or-none over these."""

    def __init__(self, blocking: list[dict[str, str]]) -> None:
        super().__init__(
            "refusing to apply: "
            + "; ".join(f"{b['superseder']} -> {b['id']} ({b['reason']})" for b in blocking)
        )
        self.blocking = blocking
```

> **Meaning-neutral, and it must stay that way.** Legs 1 and 2 are pure *admission* — they let a
> hypothesis carry an edge and be a valid endpoint; they do not change what any existing file
> means. Leg 3 is a **generic** operation fix, exercised on `interpretation`. **No hypothesis is
> stamped in this task** — that needs `superseded` in the descriptor, which is Task 8. Phase 2 does
> not change meaning, and this task does not become the exception.

> #### The lineage ruling — where supersession actually LIVES (design rev 10)
>
> The canonical edge is a **`relations:` entry** with `predicate: sci:supersedes`, authored on the
> **successor**, pointing newer → older (`consolidation.py:7-12`). It is **not** top-level
> `supersedes:` — that spelling is silently dropped (fb-2026-07-11-017).
>
> But **JSON Schema sees one record in isolation**, so it can never read an edge authored in
> *another file*. That is why `superseded_by` on the closed record is the **derived inverse**:
> written by `mark_superseded` from the canonical edge, so the closed record carries its own reason
> and validates on its own terms. **Author the edge; the inverse is written for you.** It is not a
> second authored spelling — it is the projection that makes single-record validation *possible*.

- [x] **Step 1: Write the failing gate — derived, not listed.**

```python
# science/model/tests/test_supersedable_gate.py
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.schema import RelationKind
from science_model.relations import relation_allows_kinds   # THE authoritative admission rule

# The twelve kinds that declare `superseded` while `sci:supersedes` forbids them as endpoints.
# A SHRINKING allowlist of known-broken kinds -- never a list of what to CHECK. The population is
# DERIVED below; freezing the scope instead of the debt is how a guard grows a hole by construction.
_KNOWN_HALF_WIRED: frozenset[str] = frozenset({
    "decision", "inquiry", "mechanism", "method", "observation", "plan",
    "pre-registration", "proposition", "synthesis", "theme", "topic", "workflow-step",
})


def _supersedes() -> RelationKind:
    return next(r for r in CORE_PROFILE.relation_kinds if r.name == "supersedes")


def test_every_supersedable_kind_can_author_the_CANONICAL_edge() -> None:
    # THE GATE. A kind that declares `superseded` and is auto-stamped by `mark_superseded`, but is
    # forbidden as a `sci:supersedes` endpoint, raises ValueError in materialize the moment anyone
    # authors the edge the tool itself calls canonical. The vocabulary and the relation model
    # disagree, and until this test existed, nothing noticed.
    #
    # ASK THE AUTHORITATIVE HELPER. `source_kinds & target_kinds` -- what an earlier draft computed
    # -- is NOT the admission rule: when `allowed_kind_pairs` is present it is the authoritative
    # non-Cartesian allow-list and the flat lists do not decide (`relations.py:19-33`). For
    # `supersedes` the two happen to agree on self-pairs today, so that draft got the right answer
    # from the wrong field -- which is how it would have kept agreeing right up until it didn't.
    declares = {k.name for k in CORE_PROFILE.entity_kinds if "superseded" in (k.statuses or [])}
    rk = _supersedes()
    broken = {k for k in declares if not relation_allows_kinds(rk, k, k)}

    # SUBSET, not equality. This is a ratchet on a DEBT: it must forbid the set GROWING while
    # letting any of the twelve be repaired. Exact equality would make fixing `topic` -- a strict
    # improvement -- fail the suite, which is a guard that punishes the thing it exists to cause.
    assert broken <= _KNOWN_HALF_WIRED, f"newly half-wired: {sorted(broken - _KNOWN_HALF_WIRED)}"


def test_hypothesis_is_a_supersedes_ENDPOINT() -> None:
    # DIRECT, and non-vacuous: `hypothesis` is absent from `declares` until Task 8 adds `superseded`
    # to its descriptor, so the derived gate above cannot see it yet. Without this, leg 2 would be
    # certified by a test that skips it.
    assert relation_allows_kinds(_supersedes(), "hypothesis", "hypothesis")


def test_the_hypothesis_SCHEMA_admits_the_canonical_edge() -> None:
    # Leg 1. `unevaluatedProperties: false` (Task 6) rejects every key the mixin does not declare --
    # including the ONE field D4 requires as supersession's canonical carrier. Closing the schema
    # against `relations:` would have made the terminal unreachable through the supported path.
    V.validate_as(
        _h(status="superseded", superseded_by="hypothesis:0002-y",
           relations=[{"predicate": "sci:supersedes", "target": "hypothesis:0000-old"}]),
        PROFILE,
    )


def test_a_relation_entry_is_CLOSED() -> None:
    # AuthoredTargetedRelation (source_contracts.py:18) is predicate/target/graph_layer. A typo'd
    # key inside a relation is silently dropped today -- the class of defect this arc exists to end.
    with pytest.raises(EntityValidationError):
        V.validate_as(
            _h(status="active",
               relations=[{"predicate": "sci:supersedes", "target": "hypothesis:0000-old",
                           "tarrget": "typo"}]),
            PROFILE,
        )
```

- [x] **Step 2: Run — and read WHY each one fails.** `test_hypothesis_is_a_supersedes_ENDPOINT` and
  `test_the_hypothesis_SCHEMA_admits_the_canonical_edge` fail. `test_a_relation_entry_is_CLOSED`
  **passes for the wrong reason** — `relations` is rejected wholesale by `unevaluatedProperties`,
  not because the typo was caught — which is exactly why it is paired with the admission test above
  it. The gate itself (`broken <= _KNOWN_HALF_WIRED`) **passes today**: `hypothesis` is not yet in
  `declares`, so the derived population cannot see it, and only the direct endpoint test can.

- [x] **Step 3: Leg 1 — the schema admits `relations:`.** Add to `mixin-hypothesis-1.0.json`
  `properties`, with a **closed** `$def` faithful to `AuthoredTargetedRelation`:

```json
"relations": { "type": "array", "items": { "$ref": "#/$defs/authored_relation" } }
```

```json
"authored_relation": {
  "$comment": "AuthoredTargetedRelation (source_contracts.py:18-23). The CANONICAL supersession carrier (consolidation.py:7-12) -- and `unevaluatedProperties: false` would have rejected it, making `superseded` unreachable through the only path the toolkit supports. `graph_layer` defaults to `graph/knowledge` in the model; it is optional here, never required.",
  "type": "object",
  "additionalProperties": false,
  "required": ["predicate", "target"],
  "properties": {
    "predicate": { "type": "string", "pattern": "\\S" },
    "target": { "type": "string", "pattern": "\\S" },
    "graph_layer": { "type": "string" }
  }
}
```

- [x] **Step 4: Leg 2 — the relation admits the endpoint.** In `core.py`, add `hypothesis` to the
  `supersedes` `RelationKind`'s `source_kinds`/`target_kinds` and add the
  `RelationEndpointPair(source_kind="hypothesis", target_kind="hypothesis")` pair. **Only
  hypothesis** — the other twelve are this task's declared, frozen debt, not its scope.

- [x] **Step 5: Leg 3 — the operation supplies the lineage it derives.**

> ☠️ **EVERYTHING FROM HERE TO STEP 6 IS THE DESIGN AS IT WAS SPECIFIED, NOT AS IT SHIPPED.** It is
> kept because it is the record of what six review rounds actually cost, and the argument for RULING
> 10 is unreadable without the thing that was ruled against. **Do not copy an API off it.** The
> ladder it specifies — four writer-side admission buckets, hand-derived — was DELETED (RULING 10,
> below); the shipped `SupersedesGraph` carries one field where these snippets carry four:
>
> | these snippets say | shipped |
> |---|---|
> | `graph.mismatched`, `graph.unresolved_targets`, `graph.self_referential`, `graph.cycles` | `graph.invalid: tuple[RelationDefect, ...]` — the audit's verdict, whatever rule fired |
> | `report["mismatched_kinds"]`, `report["unresolved_targets"]` | `report["invalid_relations"]` — `{code, path, subject, predicate, object, message}` |
> | a refused edge is *filed* and apply continues | a refused edge **blocks apply, corpus-wide** |
>
> `graph.archived_targets`, `graph.unmanaged_targets` and `graph.unbacked_inverses` survive
> unchanged: those are the WRITER's questions, and the writer is what this module still is.

> **The inverse is the IMMEDIATE superseder, not the chain's survivor.** Edges are
> `(superseder, superseded)` (`consolidation.py:167-172`), and a *linear* chain is a path — so in
> `A → B → C`, `A` is the survivor but the edge that closed `C` was authored by **`B`**.
> `superseded_by` is the **mechanical inversion of the authored edge**, so `C.superseded_by == B`.
> Stamping the survivor onto every member would **collapse the chain** — lossy, and an
> *interpretation* rather than an inversion. A two-node fixture cannot tell the two apart, which is
> exactly why the three-node test below exists.
>
> `SupersedesGraph` exposes `linear`/`non_linear`/`status_by_id`/`kind_by_id` and **no edge map**,
> so the inversion has to be carried out of the builder rather than reconstructed by the caller.

```python
# consolidation.py: SupersedesGraph carries everything the builder computes and today throws away --
# the inversion, the authored inverse it must reconcile AGAINST, and all three edge-admission
# outcomes. The builder is the SOLE authority on which edges are real; nothing downstream recomputes
# an admission decision, and nothing downstream consults `known` again.
@dataclass(frozen=True)
class SupersedesGraph:
    linear: tuple[SupersededChain, ...]
    non_linear: tuple[NonLinearComponent, ...]
    status_by_id: Mapping[str, str | None]
    kind_by_id: Mapping[str, str]         # LIVE entities -- the population `mark_superseded` stamps
    path_by_id: Mapping[str, Path]        # LIVE entities -- `Result` reports a FILE, not an id
    edges: frozenset[tuple[str, str]]     # every ADMITTED (superseder, superseded) edge, canonical
    superseder_by_id: Mapping[str, str]   # superseded id -> its IMMEDIATE superseder (linear only)
    superseded_by_id: Mapping[str, str]   # superseded id -> the AUTHORED inverse, CANONICALIZED
    mismatched: tuple[dict[str, str], ...]        # edge the RELATION MODEL forbids
    archived_targets: tuple[dict[str, str], ...]  # edge resolves INTO the archive -- historical
    unmanaged_targets: tuple[dict[str, str], ...]   # edge resolves, but to nothing WE can stamp
    unresolved_targets: tuple[dict[str, str], ...]  # edge resolves NOWHERE -- dangling
    unbacked_inverses: tuple[dict[str, str], ...]   # authored inverse with NO admitted edge behind it
```

> `kind_by_id` and `path_by_id` are **live-only, and deliberately so** — they are the writer's map of
> what it can stamp. The *legality* question needs kinds for targets we will never stamp (archived
> rows, commons entities), and that map is a different map, on `IdResolution`, spanning a different
> population. Merging them would be the whole bug in finding 2 again, wearing a dataclass field.

> `edges` is on the graph because the **unbacked-inverse** rule and the `validate` check are both
> *consumers* of the admission decision, not second opinions about it. Exposing the admitted set is
> what lets them ask "is there an edge behind this?" without ever re-deciding what an edge is.

```python
# consolidation.py -- the resolution bundle. The builder stays a PURE function of its inputs: it
# resolves through this and never touches the filesystem, so every test constructs one directly.
@dataclass(frozen=True)
class IdResolution:
    """How an authored reference becomes a canonical id, and WHO OWNS that id.

    It carries the CONFIGURED RESOLVER, not a token dump. An earlier draft enumerated
    `live ∪ manual_aliases` into a `canonical` dict -- and per-entity `aliases`/`same_as` are in
    NEITHER collection: they are registered inside `build_alias_map` (`sources.py:653-658`), which
    the resolver owns. So that draft's own live-alias test could not have passed. Ask the resolver
    the question; do not try to reconstruct what it knows.

    Resolvability and ownership are ORTHOGONAL, and conflating them is the second bug this shape
    fixes. `mutable` is the LIVE MARKDOWN scan -- not `sources.entities`, which also carries
    commons-overlay and non-markdown entities that `iter_entity_frontmatter` never saw and
    `kind_by_id` has no key for.

    And LEGALITY is orthogonal to BOTH, which is the third. `kind_of` spans EVERY population the
    resolver can reach -- live, archived, and everything else in `sources.entities` -- because that is
    the population `materialize` validates a relation endpoint against: it reads `object_entity.kind`
    for whatever the reference resolved to, live or not (`materialize.py:1721`). A kind map that
    stopped at the live scan could not ask the legality question about the very targets we decline to
    stamp -- so those edges would skip the check entirely. See the box below.
    """

    resolver: ReferenceResolver    # the SAME object, with the SAME args, that `materialize` uses
    mutable: frozenset[str]        # canonical ids of LIVE MARKDOWN entities -- the only stampable set
    archived: frozenset[str]       # canonical ids of ACTIVE archived rows
    kind_by_id: Mapping[str, str]  # kind of EVERY id ANY population backs -- live, archived, or other

    def canonical(self, raw: str) -> str | None:
        res = self.resolver.resolve(raw)
        return res.canonical_id if res.status == "resolved" and res.canonical_id else None

    def kind_of(self, canonical_id: str) -> str | None:
        """The kind of a RESOLVED id, or None if NOTHING backs it.

        `None` is a real answer, not a lookup miss. `build_alias_map` registers manual aliases
        UNCONDITIONALLY -- `_register_alias(alias_map, alias, canonical_id)` (`sources.py:660-662`) --
        so an alias resolves to its canonical id whether or not any record backs that id. Such a
        target is dangling with extra steps: we know nothing about it, we cannot ask whether the edge
        is legal, and it must BLOCK rather than settle into benign `unmanaged` debt.

        `""` IS A DIFFERENT ANSWER FROM `None`: a record backs the id, but declares no kind (an
        archive row predating the field). Materialize resolves that to `""` too, and `""` satisfies no
        `allowed_kind_pairs` entry -- so the edge is MISMATCHED, not dangling. Distinguishing the two
        is what keeps this authority's refusals identical to materialize's.
        """
        return self.kind_by_id.get(canonical_id)
```

```python
# ...built from the same edges, for linear chains only. Non-linear components have an ambiguous
# survivor -- they are already skipped, and they must not acquire a lineage claim here.
    superseder_by_id: dict[str, str] = {}
    for chain in linear:
        members = {chain.survivor, *chain.superseded}
        for src, dst in edges:
            if src in members and dst in members:
                superseder_by_id[dst] = src   # a linear chain is a path: exactly one in-edge
```

> #### A derived field must not be *expressible* as caller input
>
> **`edit_entity` does not gain a `superseded_by` parameter.** An earlier draft added one — and
> `edit_entity` is the **authored**-edit surface, reached from `science entity edit`. Putting a
> *derived* field on it would recreate, in the same commit that rules it derived, the **second
> authored spelling** rev 10 exists to eliminate: an author could write a resolvable
> `superseded_by` with **no canonical edge behind it**, and the schema would pass, and
> `check_resolution` would pass, and the entity would be superseded according to *nothing*. The
> lineage would be true and groundless at once — which is the precise failure `supersedes:` was
> deleted for.
>
> **A second draft moved the field to its own writer, `stamp_supersession(project_root, ref, *,
> superseded_by: str)`, and called the problem solved. It was not.** "No CLI flag reaches it" is a
> statement about *one* caller. The signature still takes the derived fact **as caller input**, so
> any Python caller — a script, a future consumer, **and Task 10's own test, which did exactly
> this** — can hand it an existing, resolvable id with no canonical edge behind it. Schema passes.
> `check_resolution` passes. The lineage is groundless, and the guard we wrote against the *authored*
> spelling has been walked around by the *derived* one. **A field nobody can author is not the same
> as a field nobody can pass.**
>
> Verifying the backing edge inside the writer would only paper over it: the builder is already the
> sole authority on which edges are real (it is the thing that admits, refuses, and classifies them),
> and a second check there would be a duplicate authority that can disagree with the first.
>
> **So the derived writer takes the graph, not the string.** It is module-private to
> `consolidation`, and it reads the superseder out of `graph.superseder_by_id` — which is populated
> from the admitted canonical edges and nothing else. There is no argument to corrupt, so the
> violation is **unexpressible**, not merely unreached.
>
> > **A third draft nearly gave it back.** It split the boundary into a *public*
> > `prepare_entity_write(project_root, ref, **fields)` and made `edit_entity` a `**fields`
> > passthrough — and then "proved" the field was unreachable with
> > `assert "superseded_by" not in inspect.signature(edit_entity).parameters`. **Both calls below
> > work, and the assertion passes anyway:**
> >
> > ```python
> > prepare_entity_write(root, "hypothesis:0001-x", superseded_by="hypothesis:0002-y")  # public
> > edit_entity(root, "hypothesis:0001-x", superseded_by="hypothesis:0002-y")           # **fields
> > ```
> >
> > `**kwargs` does not just *fail* to close the door — it makes a named-parameter test
> > **anti-informative**, because the absence of the name is exactly what a `VAR_KEYWORD` signature
> > guarantees whether or not the field is reachable. A guard that passes *because* the hole is open
> > is worse than no guard.
>
> **So there is no public prepare at all.** The unrestricted mechanism is private, the authored
> surface is explicit and keyword-only, and the derived writer is the mechanism's only other caller:

```python
# entities.py -- ONE boundary, in two halves, and BOTH halves are PRIVATE.
#
# `_prepare_write` is the mechanism: it merges whatever frontmatter it is given, renders, validates,
# and writes NOTHING. It takes a `fields` MAPPING and has NO `**kwargs` -- so the one place a
# derived field can be set is a call site, and there are exactly two of them in the codebase.
#
# The split (rather than one validate-then-write function) is what makes `mark_superseded`'s
# all-or-none claim true rather than aspirational: a caller can learn that a write WOULD be rejected
# before a byte hits the disk. Task 10 puts the schema + resolution checks INSIDE `_prepare_write`,
# so both entry points inherit them and neither can be validated after the fact.
#
# THE COMMIT HALF IS PRIVATE TOO, AND SO IS THE VALUE IT TAKES. An earlier draft made both public:
# `PreparedWrite` is a plain frozen dataclass, so it is freely constructible, and a PUBLIC
# `commit_entity_write` will write whatever `.text` it is handed -- by contract, WITHOUT validating
# it. That is not a hole in the boundary; it IS a second, unvalidated writer, and the shortest path
# through it is one line:
#
#     commit_entity_write(PreparedWrite(entity_id=..., path=..., text="<anything>", warnings=()))
#
# A boundary whose "already validated, nothing left to check" half is reachable from outside has
# simply moved the front door.
#
# SO THE TOKEN CARRIES A SEAL, because a frozen dataclass alone is NOT unforgeable -- a plain
# `_PreparedWrite(entity_id=..., path=..., text="<anything>", warnings=())` is one call, and privacy by
# underscore is a convention the interpreter does not enforce.
#
# AND THE SEAL IS BOUND TO THE PAYLOAD, not merely POSSESSED. A bare sentinel -- "hold this object and
# you are trusted" -- is a BEARER token, and a bearer token can be carried onto content it never
# vouched for, WITHOUT any private import at all:
#
#     dataclasses.replace(legitimately_prepared, text="<anything>")   # <- copies the sentinel; passes
#
# `replace()` re-runs `__post_init__`, so an identity check on a sentinel sees the SAME trusted object
# and waves through text that never met `_schema_validate_or_raise`. The seal must therefore be a
# statement ABOUT THE TEXT: an HMAC over the payload, keyed by a per-process secret. Mutate any field
# it covers and the seal no longer matches what it seals -- `replace()` recomputes nothing, so it
# carries the OLD seal onto NEW text and `__post_init__` refuses it.
#
# CONSTRUCTION-TIME VERIFICATION IS NOT THE WRITE BOUNDARY. Python erases the `_PreparedWrite` type
# annotation at runtime, so `_commit_write` can otherwise be handed a duck-typed object that never
# ran `__post_init__`. And a legitimately prepared frozen instance can still be changed deliberately
# with `object.__setattr__` after its constructor check ran. `_commit_write` therefore requires the
# concrete token type AND recomputes the HMAC immediately before the atomic replace. The constructor
# check fails early; the commit check is authoritative for the bytes about to be written.
#
# THE HONEST CLAIM, since Python has no private constructors: this does not make forgery *impossible*
# -- `entities._SEAL_KEY` is reachable by anyone willing to import a private name from another module
# and recompute the digest. It makes forgery **inexpressible by accident**: not by a plausible
# refactor, not by a helpful `replace()`, not by a caller who thought this was the supported path.
# That is the strongest form the guarantee takes in this language, and it is stated as such rather
# than as the absolute an earlier draft implied.
import hashlib
import hmac
import secrets

_SEAL_KEY = secrets.token_bytes(32)   # module-private, per-process; never exported, never persisted


def _seal(entity_id: str, path: Path, text: str) -> str:
    """An HMAC over EVERY field the write actually consists of. Covering `text` alone would leave
    `replace(prepared, path=<elsewhere>)` free to redirect validated bytes at an unvalidated file."""
    payload = "\0".join((entity_id, str(path), text)).encode("utf-8")
    return hmac.new(_SEAL_KEY, payload, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class _PreparedWrite:
    entity_id: str
    path: Path
    text: str                      # fully rendered, fully validated -- nothing left to decide
    warnings: tuple[str, ...]
    seal: str                      # HMAC of (entity_id, path, text). No default: see the guard test.

    def __post_init__(self) -> None:
        # `compare_digest`, not `==`: this is a MAC check, and constant-time comparison is what a MAC
        # check is. Runs on `replace()` too, which is the entire point.
        if not hmac.compare_digest(self.seal, _seal(self.entity_id, self.path, self.text)):
            raise TypeError(
                "_PreparedWrite is not constructible, and its seal does not travel: it is the proof "
                "that _prepare_write validated THIS text for THIS path. Call _prepare_write."
            )


def _prepare_write(project_root: Path, ref: str, fields: Mapping[str, object]) -> _PreparedWrite:
    """PRIVATE. Merge, render, validate, SEAL. Writes NOTHING. Callers: `edit_entity` (which cannot
    express `superseded_by`) and `consolidation._prepare_supersession` (which derives it)."""


def _commit_write(prepared: _PreparedWrite) -> EntityWriteResult:
    """PRIVATE. Authenticate the prepared value, then atomically replace the file. It performs no
    schema or resolution decisions; it re-verifies the proof that those decisions covered THESE
    bytes for THIS path. A type annotation alone is not a runtime capability check."""
    if not isinstance(prepared, _PreparedWrite):
        raise TypeError("a prepared write must be earned from _prepare_write")
    if not hmac.compare_digest(
        prepared.seal, _seal(prepared.entity_id, prepared.path, prepared.text)
    ):
        raise TypeError("prepared-write seal does not cover the bytes and path being committed")
    _atomic_replace_text(prepared.path, prepared.text)
    return EntityWriteResult(entity_id=prepared.entity_id, path=prepared.path,
                             warnings=list(prepared.warnings))


# THE AUTHORED SURFACE. Explicit, keyword-only, and it must NEVER grow a `**kwargs` -- see Task 10
# for the full signature, the enforcement, and the guards that pin every one of these properties.
def edit_entity(project_root: Path, ref: str, *, title: str | None = None, ...) -> EntityWriteResult:
    ...   # NO `superseded_by`, and NO VAR_KEYWORD to smuggle it through
```

```python
# consolidation.py -- the DERIVED-projection writer. Private, and it takes the GRAPH.
# `superseded_by` is never a parameter: it is READ from the admitted canonical edge. That is the
# whole guarantee -- a derived value that no caller can supply cannot drift from the fact it projects.
def _prepare_supersession(project_root: Path, graph: SupersedesGraph, member: str) -> _PreparedWrite:
    """Prepare `status: superseded` + its derived inverse for one member. Writes NOTHING."""
    return _prepare_write(
        project_root, member,
        {"status": _SUPERSEDED,
         "superseded_by": graph.superseder_by_id[member]},   # <- from the edge; never from a caller
    )
```

**At the start of Step 5, write these failing authentication tests before implementing the boundary.**
They land in this task, beside the boundary they exercise — not in Task 10, two commits after the
unchecked writer first exists:

```python
# science/tests/test_entity_commands.py
import dataclasses
from inspect import Parameter, signature
from types import SimpleNamespace


def test_a_PreparedWrite_cannot_be_CONSTRUCTED_only_earned() -> None:
    # The AST guards pin call sites inside this repo. They say nothing about a caller that constructs
    # the token itself. Python has no absolute privacy, but an invalid token must fail immediately.
    with pytest.raises(TypeError, match="not constructible"):
        _PreparedWrite(entity_id="hypothesis:0001-x", path=Path("x.md"),
                       text="anything at all", warnings=(), seal="not-a-seal")


def test_the_seal_does_NOT_TRAVEL_to_content_it_never_vouched_for(tmp_project) -> None:
    prepared = _prepare_write(tmp_project, "hypothesis:0001-x", {"title": "legitimate"})

    with pytest.raises(TypeError, match="does not travel"):
        dataclasses.replace(prepared, text="superseded_by: whatever-i-like\n")
    with pytest.raises(TypeError, match="does not travel"):
        dataclasses.replace(prepared, path=tmp_project / "entities/hypotheses/0002-y.md")

    # Control: the guard admits the value whose payload is unchanged.
    assert _commit_write(prepared).entity_id == "hypothesis:0001-x"


def test_commit_refuses_an_object_that_only_LOOKS_prepared(tmp_project) -> None:
    # The annotation is erased at runtime. Attribute compatibility is not authentication.
    fake = SimpleNamespace(
        entity_id="hypothesis:0001-x",
        path=tmp_project / "entities/hypotheses/0001-x.md",
        text="superseded_by: whatever-i-like\n",
        warnings=(),
    )
    with pytest.raises(TypeError, match="earned from _prepare_write"):
        _commit_write(fake)  # type: ignore[arg-type] -- the runtime boundary is the subject


def test_commit_RECHECKS_the_seal_after_construction(tmp_project) -> None:
    # `frozen=True` blocks ordinary assignment, not mutation through Python's object protocol. The
    # commit boundary must authenticate the state it consumes, not trust a check that ran earlier.
    prepared = _prepare_write(tmp_project, "hypothesis:0001-x", {"title": "legitimate"})
    object.__setattr__(prepared, "text", "superseded_by: whatever-i-like\n")

    with pytest.raises(TypeError, match="seal does not cover"):
        _commit_write(prepared)


def test_the_SEAL_is_never_a_default_and_never_exported() -> None:
    assert signature(_PreparedWrite).parameters["seal"].default is Parameter.empty
    exported = set(getattr(entities, "__all__", ()))
    assert {"_SEAL_KEY", "_seal", "_PreparedWrite", "_prepare_write", "_commit_write"} & exported == set()
```

Construction-time and consumption-time checks are deliberately separate. `__post_init__` makes
ordinary construction and `dataclasses.replace` fail early; `_commit_write` is authoritative for
the concrete object, payload, and path at the instant the write occurs. A test introduced later
cannot protect the interval in which the writer already exists.

It goes through the same `find_entity` / render / validate path `edit_entity` uses, so **Task 10's
schema boundary governs it too** — one boundary, two entry points. What it does *not* do is give the
boundary a groundless input to reject, because no such input can be constructed. That is a
strengthening, not a gap: **the strongest form of a guard is a signature in which the violation
cannot be written** — which is only true if the signature is closed, and closing it is the whole
reason `_prepare_write` is private and `edit_entity` is explicit.

> #### An illegal edge must be rejected BEFORE the topology is classified — not inside it
>
> An earlier draft checked `relation_allows_kinds` inside the `graph.linear` loop. **That check can
> never fire on the case it was written for.** An illegal edge is still an *edge*: it joins the
> component and it counts toward in-degree. Executed against the real classifier:
>
> ```
> interpretation:new  -> interpretation:old     # LEGAL
> workflow-run:x      -> interpretation:old     # ILLEGAL
>
> _classify(...) == (False, None, {"interpretation:old"})      # in_deg[old] == 2 -> NON-LINEAR
> ```
>
> The component never reaches `graph.linear`, so the guard never runs, `mismatched_kinds` comes back
> **empty** — and the **legal** supersession is silently suppressed along with it, misfiled as a
> *"branched or cyclic supersedes chain"* when nothing branched: **one of its edges was not a
> supersession at all.** A guard that runs downstream of the corruption it detects is not a guard.
>
> So the pair rule is applied **in the builder, at edge admission** — which is also where the
> pre-existing `if dst not in known: continue` filter lives, and that filter is the next thing to
> fix. An edge the relation model forbids is **not an edge**: it is excluded from the topology,
> carried out on the graph, and the remaining legal edges classify normally — so the legal chain
> above is correctly linear, and the illegal edge is *reported* rather than absorbed into a
> misdiagnosis.

> #### `if dst not in known: continue` — the filter that made a claim true by deleting its
> counterexamples
>
> Today the builder drops any edge whose target is not in the live scan, **silently**. It is why
> Task 10 could assert that a derived inverse "always resolves and cannot dangle" — the *canonical
> edge* that would have dangled never became an edge, so the invariant held by **deleting the
> evidence against it**, with no finding anywhere. That directly contradicts this task's own
> contract that report mode "always enumerates everything", and it contradicts all-or-none: a
> corpus with a supersession pointing at nothing applies cleanly and reports green.
>
> **`not in known` is not one state. It is three**, and the live scan cannot tell them apart because
> `iter_entity_frontmatter` calls `iter_entity_markdown` **without** `include_archived`
> (`entity_scan.py:19`) — so the archive is invisible to it, exactly like a typo:
>
> | target | what it is | admission | apply |
> |---|---|---|---|
> | **live** | an ordinary entity | **admit** — classify it | mutable |
> | **archived** (`entities/_archive/`, in the archive index) | a **valid historical** supersession; the record exists, and it is **frozen** | **refuse the edge** — report it under `archived_targets` | **no mutation** (`entities._reject_if_archived` would refuse the write anyway — better to never plan it) |
> | **nowhere** (neither live nor archived) | a **dangling canonical edge** — the relation names an id that does not exist | **refuse the edge** — report it under `unresolved_targets` | **refuse: apply writes nothing** |
>
> **And "is it live / archived / nowhere" is a question about a CANONICAL ID, not about a string.**
> An earlier draft answered it with `dst in known` and `dst in load_archive_index(...).active_by_id` —
> raw membership against canonical ids on both sides. **The authoritative path does not work that way.**
> `load_project_sources` builds a `ReferenceResolver` over live entity `aliases`/`same_as` *and* folds
> every archived alias in via `ArchiveIndex.resolvable_ids()` (`sources.py:610-626`); `materialize`
> then resolves each relation target through it and canonicalizes before touching the graph
> (`materialize.py:1619-1627`). So an entity referred to by an alias — a rename, a `same_as` merge, an
> archived row's recorded alias — **materializes perfectly well**, and the string-membership draft
> would have called that same edge `unresolved` and **blocked apply on it**. A false positive on a
> blocking error is strictly worse than the silent drop it replaced: it turns a working corpus into a
> refused one.
>
> So the builder **canonicalizes first, then classifies**, through the same two authorities the
> materializer uses — `ArchiveIndex.resolvable_ids()` (not `active_by_id`) and the live alias map.
> Three answers, and **no state is silent** — but every one of them is an answer about the canonical
> id the reference actually denotes.
>
> **The middle row is not hypothetical — it is the sanctioned path's own output.** `archive_entities`
> selects candidates *by status* (`archive.py:118-128`), and `superseded` is one of them. So the
> ordinary end of a lineage is: author the edge → `mark_superseded` stamps `i-old` → `science entities
> archive` relocates it under `_archive/`. The superseder keeps its canonical `sci:supersedes` edge,
> pointing at a record that is now invisible to `iter_entity_frontmatter`. **Every project that
> archives a superseded entity produces this state**, and today the very next `mark_superseded` run
> drops that edge without a word. There is also nothing left to do about it: the archive row *carries*
> `superseded_by` (`archive.py:140`), so the lineage went into the archive intact.
>
> **Archived is therefore not an error.** The edge is true, the record exists, its projection is
> already correct, and it is frozen. It reports and does not block. **Unresolved is an error**, and it
> blocks apply for the same reason a mismatch does.
>
> **Apply is ALL-OR-NONE over graph-admission errors.** If any edge is `mismatched` or `unresolved`,
> `apply=True` writes **nothing** — not the unaffected components either. `mark_superseded` derives
> corpus-wide state from an authored graph; if part of that graph is not a graph, the derivation is
> not trustworthy anywhere, and a partial write leaves a corpus that is neither the old state nor the
> new one. Report mode (`apply=False`) always enumerates everything — mismatches, unresolved,
> archived, chains, repairs — because *diagnosis must never be gated on the thing being diagnosable.*
> (Fail early; no silent fallbacks. And it composes with Task 9's two-phase all-or-none migration
> rather than fighting it.) **The precise scope of "all-or-none" — and what it does *not* promise —
> is pinned in its own box below; it is a claim that has to be earned by the write loop, not just
> asserted here.**

> #### The fourth outcome: an inverse that RESOLVES and is still groundless
>
> Everything above is about the **edge**. This is about the **projection**, and it is the case the
> plan named as the whole reason `superseded_by` is derived — then failed to catch:
>
> ```yaml
> # hypothesis:0001-x  -- a hand edit, or a file that predates the rule
> status: superseded
> superseded_by: hypothesis:0002-y     # 0002-y EXISTS. There is no `sci:supersedes` edge anywhere.
> ```
>
> Trace it through every net this plan claims:
>
> | net | verdict | why |
> |---|---|---|
> | JSON Schema | **passes** | `superseded_by` is a non-empty string, and it discharges `superseded`'s `anyOf` |
> | `check_resolution` (Task 7) | **passes** | the id **resolves** — it only ever caught *dangling* refs |
> | `mark_superseded` reconciliation | **never looks** | `0001-x` has no in-edge, so it is in no chain, so no loop above ever visits it |
> | the write boundary | **never sees it** | nothing can hand a groundless inverse to a writer any more — which also means nothing arrives for it to reject |
>
> **Four nets, zero coverage.** The previous revision even said "`check_resolution` FAILS validate when
> no canonical edge exists" — but `check_resolution` cannot see edges; it sees *references*, and this
> one resolves. **That claim was true only for a dangling id, and it was written as though it were true
> in general.** The lineage is exactly the thing rev 10 deleted `supersedes:` to prevent — *true and
> groundless at once* — and it survived a revision whose entire subject was that failure.
>
> So the builder derives a **fourth** outcome. It already knows every admitted edge; an authored
> inverse with no matching edge among them is `unbacked`:
>
> ```
> unbacked(id)  ⇔  authored superseded_by(id) = S  ∧  (S, id) ∉ admitted_edges
> ```
>
> **This is not a second edge authority — it is a consumer of the first.** The check is
> `(S, id) not in graph.edges`, and `graph.edges` is what the builder admitted. The validator consumes
> `SupersedesGraph` for the same reason: one authority, several readers.
>
> It **blocks apply** (the derivation is corpus-wide; an authored inverse contradicting the graph means
> the corpus disagrees with itself about what supersedes what), and it surfaces in `validate` as
> `<kind>.unbacked-inverse` — **WARN now, ERROR at Task 12's ratchet**, alongside
> `hypothesis.dangling-lineage`.
>
> ⚠️ **The roster does NOT author zero `superseded_by`, and an earlier version of this box said it
> did.** Four live records carry one with no edge behind it — one `3d-attention-bias` interpretation
> and three in `natural-systems` — because their real lineage is written in the **withdrawn top-level
> `supersedes:` spelling** the Entity model silently drops. They are this rule's findings on disk
> today, and Task 9's migration input. That is why the tier is WARN: ERROR would break `validate` in
> two projects for a defect they have no migration for yet.
>
> Note the edge set must be compared **against non-linear components too** — an id inside a branched
> component *has* an in-edge, so it is backed even though it is never stamped. Comparing against
> `superseder_by_id` (linear-only) would report every non-linear member as unbacked. The comparison is
> against `edges`, which is why `edges` is what the graph carries.

```python
# consolidation.py -- the RESOLUTION bundle, built with the SAME CALL the materializer makes.
# Not a reimplementation of it: `ReferenceResolver.from_entities(entities, manual_aliases=...,
# identity_table=...)` is materialize.py:349, verbatim. Same three arguments, same answers -- which is
# the only way "an edge that materializes must not be reported unresolved" can be a guarantee rather
# than a coincidence. (`sources.manual_aliases` ALREADY has the archive's `resolvable_ids()` folded in
# at sources.py:626, so archived aliases resolve too.)
def _id_resolution(project_root: Path, entries: list[tuple[Path, dict[str, Any]]]) -> IdResolution:
    from science_tool.archive import load_archive_index
    from science_tool.graph.identity_table import build_identity_table
    from science_tool.graph.reference_resolution import ReferenceResolver
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(project_root)
    resolver = ReferenceResolver.from_entities(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        identity_table=build_identity_table(sources),   # <- materialize passes this; so do we
    )

    def canon_or_self(raw: str) -> str:
        res = resolver.resolve(raw)
        return res.canonical_id if res.status == "resolved" and res.canonical_id else raw

    # THE KIND MAP SPANS EVERY POPULATION THE RESOLVER CAN REACH, because the LEGALITY question is
    # about the resolved ENTITY, not about whether we can write to it. Three sources, live last so it
    # wins -- it is the only one that reflects what is on disk right now:
    #
    #   1. `sources.entities`  -- commons overlay, non-markdown adapters. Carries `.kind`. This is
    #      literally the population `materialize` reads `object_entity.kind` from.
    #   2. the ARCHIVE INDEX   -- archived markdown is NOT loaded as an entity (`sources.py:610-613`),
    #      so it is in NEITHER `sources.entities` nor the live scan. `ArchiveRow.kind` is NULLABLE
    #      (`archive.py:32`), and the empty string is what materialize makes of that:
    #      `_ArchivedEndpoint(..., kind=arow.kind or "")` (`materialize.py:1626`). MIRROR IT EXACTLY --
    #      do NOT fall back to the id prefix. `supersedes` declares `allowed_kind_pairs`, which is an
    #      authoritative allow-list, so `""` matches no pair and materialize RAISES on the edge. A
    #      prefix fallback here would ADMIT and STAMP an edge the graph then refuses to build: the
    #      write would succeed and the corpus would break at materialization, which is the worst of
    #      both. The two authorities must refuse the SAME corpus, so a kind-less archive row lands in
    #      `mismatched` and BLOCKS -- exactly as it does downstream.
    #   3. the LIVE SCAN       -- authoritative for what exists now. Prefix fallback is right HERE:
    #      it is what `_kind_of` already does, and a live entity's `kind` is required by the model, so
    #      the fallback only ever covers frontmatter the loader would have rejected anyway.
    archive = load_archive_index(project_root)
    kind_by_id: dict[str, str] = {}
    for entity in sources.entities:
        kind_by_id[entity.canonical_id] = entity.kind
    for cid, row in archive.active_by_id.items():
        kind_by_id[cid] = row.kind or ""        # <- materialize.py:1626, verbatim
    for _path, fm in entries:
        eid = canon_or_self(str(fm["id"]))
        kind_by_id[eid] = _kind_or_prefix(eid, fm.get("kind"))

    # MUTABLE = the MARKDOWN SCAN, canonicalized. NOT `sources.entities`: that list also carries
    # commons-overlay and non-markdown entities which `iter_entity_frontmatter` never yielded, so
    # the graph's live `kind_by_id`/`path_by_id` have no key for them -- classify one as stampable and
    # the next line KeyErrors.
    return IdResolution(
        resolver=resolver,
        mutable=frozenset(canon_or_self(str(fm["id"])) for _path, fm in entries),
        archived=frozenset(archive.active_by_id),
        kind_by_id=kind_by_id,
    )


def _kind_or_prefix(entity_id: str, declared: str | None) -> str:
    """The declared kind, else the id prefix. `_kind_of` delegates here; ids are `<kind>:<slug>`."""
    return str(declared or entity_id.split(":", 1)[0])
```

> #### Resolvable ≠ ours ≠ legal. THREE questions, and each draft has collapsed a different pair.
>
> An earlier draft classified with `if dst not in resolution.live:` and treated everything that fell
> through as **archived** — "an id cannot resolve to neither." **It can.** A project's manual aliases,
> its commons overlay, and its non-markdown sources all put ids into the resolver that are in neither
> the live markdown scan nor the archive index. The draft would have filed such a target as a frozen
> archived record — and, one line later, indexed `kind_by_id[dst]` for a key that was never there.
>
> The draft that *fixed* that then collapsed the other pair: it answered **ownership first** and
> `continue`d, so `relation_allows_kinds` was **downstream of the archived and unmanaged branches and
> could never fire on them**:
>
> ```
> interpretation:new  sci:supersedes  dataset:commons-thing     # ILLEGAL PAIR
>   -> resolves (commons overlay) -> not mutable -> `unmanaged_targets` -> reported BENIGN, apply proceeds
> ```
>
> **`materialize` rejects that edge** (`_validate_authored_relation_endpoint`, `materialize.py:1721`,
> `ValueError`) — and it does so against `object_entity.kind` for *whatever the reference resolved to*,
> live or not. Ownership is not one of its inputs. So an illegal edge into the archive or into commons
> would sail past the one check written to catch it, and the corpus would only break later, at graph
> build, with no finding from the surface that had the edge in its hand.
>
> **This is the plan's own lesson, one layer up.** Three boxes above, an illegal edge had to be
> refused *before* `_connected_components` because "a guard that runs downstream of the corruption it
> detects is not a guard." Putting the ownership `continue` in front of the pair check moved the same
> guard downstream of the same corruption. The fix is the same fix: **decide legality first, on the
> resolved entity — then decide who owns it.**
>
> | resolves? | backed by a record? | pair legal? | outcome | blocks apply? |
> |---|---|---|---|---|
> | no | — | — | `unresolved_targets` — dangling | **yes** |
> | yes | **nothing** (a manual alias to an id no record backs) | *unanswerable* | `unresolved_targets` — dangling with extra steps | **yes** |
> | yes | yes | **no** | `mismatched` — the relation model forbids it | **yes** |
> | yes | live markdown | yes | **admit** — classify it | — |
> | yes | the archive index | yes | `archived_targets` — historical, frozen | **no** |
> | yes | neither (commons, non-markdown) | yes | `unmanaged_targets` — resolves; no markdown file *here* to stamp | **no** |
>
> Row 2 is the reviewer's alias-with-no-record, and it blocks: with no record we have no kind, with no
> kind the legality question is *unanswerable*, and an unanswerable guard must not report **benign**.
> Note what rows 5 and 6 now mean — they are `archived`/`unmanaged` **and legal**. "We won't stamp it"
> is a statement about our write scope; it was never a licence to skip the edge's own validity.

```python
# consolidation.py -- build_supersedes_graph's preamble. The LIVE maps, canonicalized. `consolidation.py:158-165`
# builds `status_by_id`/`kind_by_id` today keyed on the RAW id and drops `path` on the floor; both change.
# `path_by_id` exists because `Result` reports a FILE (`result.py:24-30`), and the validate check must not
# re-derive the canonicalization that produced the key it looks up.
    status_by_id: dict[str, str | None] = {}
    kind_by_id: dict[str, str] = {}
    path_by_id: dict[str, Path] = {}
    for path, fm in entries:
        eid = resolution.canonical(str(fm["id"])) or str(fm["id"])
        status_by_id[eid] = fm.get("status")
        kind_by_id[eid] = _kind_or_prefix(eid, fm.get("kind"))
        path_by_id[eid] = path
```

```python
# consolidation.py -- build_supersedes_graph(inputs). RULING 10: THE LADDER IS GONE.
#
# ☠️ THERE IS NO ADMISSION LOGIC HERE ANY MORE, and that is the entire point. This function used to
# ask, by hand, every question `materialize` asks of a relation -- resolvable? backed? an edge at all?
# a legal pair? acyclic? -- and it got a NARROWER answer six times in a row, in six review rounds. The
# questions are now asked ONCE, by `admit_authored_relation`, which IS the graph builder's admission,
# and this module consumes the verdict.
#
# What is left is the ONE question this module is the authority on:
#
#       the edge is REAL -- CAN WE STAMP THE THING IT POINTS AT?
#
# `archived` and `mutable` are the WRITER's populations. There is deliberately no kind map, no
# resolver walk, and no cycle scan in this file.
    edges: set[tuple[str, str]] = set()          # ADMITTED *and* STAMPABLE. A set: an RDF graph is a
    archived_targets: list[dict[str, str]] = []  #   set of triples, so the same edge authored twice
    unmanaged_targets: list[dict[str, str]] = [] #   is ONE edge, and a list would fake a branch.

    for admitted_relation in audit.relations("supersedes"):   # <- ONLY relations MATERIALIZE ADMITTED
        src = admitted_relation.subject.canonical_id
        dst = admitted_relation.object_canonical_id
        path_of_edge = admitted_relation.relation.source_path  # WHERE THE LINE IS: `relations.yaml`,
        if dst is None:                                        #   or the subject's markdown
            continue          # an EXTERNAL term: a real edge, but not a node -- nothing to stamp

        if dst in resolution.archived:
            # A VALID historical supersession into a frozen record -- the ordinary end of a lineage
            # (supersede, then archive). Report it, keep it out of the topology, do NOT block.
            archived_targets.append({"id": dst, "superseder": src, "path": path_of_edge,
                                     "reason": "target is archived (frozen); no live record to stamp"})
            continue
        if dst not in resolution.mutable:
            # ADMITTED, but not ours: a commons-overlay entity, a non-markdown source. `materialize`
            # builds this edge happily; we simply have no markdown file here to write.
            unmanaged_targets.append({"id": dst, "superseder": src, "path": path_of_edge,
                                      "reason": "target resolves but is not a live markdown entity "
                                                "of this project; nothing here to stamp"})
            continue
        edges.add((src, dst))

    # The audit already found the cycles -- over the {amends, supersedes} FAMILY, over every RESOLVED
    # edge. This module only has to BELIEVE it. A component touching a cyclic node is not a chain and
    # not a branch: it is a corpus with no graph. And note it CANNOT be recomputed from `edges`, which
    # is the writer's set and drops the very archived/commons edges a cycle can run through -- which
    # is exactly why the cycle question does not live in this file.
    cyclic_nodes = frozenset(n for d in audit.defects if d.code == "cycle"
                             for n in (d.subject, d.object))
    ...
    for comp in _connected_components(nodes, admitted):
        if comp & cyclic_nodes:
            continue    # already diagnosed, and diagnosed BETTER. Nothing in a cycle is stampable.
```

> **Why `archived`/`unmanaged` edges stay out of the topology even though they are now *validated*.**
> Legality and topology are still separate: an admitted edge is one whose *superseded* endpoint is a
> file we can stamp, and the point of `edges` is to drive the stamping. An archived target is frozen;
> a commons target is not ours. Including either would put a node in a component that
> `_classify` would then count in-degree for — and `mark_superseded` would plan a write against a
> record that has no file here. They are *reported*, in full, and they are *checked*; they are simply
> not stampable, which is a different sentence.

```python
# consolidation.py -- the FOURTH outcome, derived from the admitted edges and nothing else.
# Compared against `edges` (ALL admitted edges), NOT `superseder_by_id` (linear chains only): a member
# of a BRANCHED component has a real in-edge and is therefore backed, even though it is never stamped.
    admitted = set(edges)
    unbacked_inverses: list[dict[str, str]] = []
    for _path, fm in entries:
        raw_inverse = fm.get("superseded_by")
        if not isinstance(raw_inverse, str) or not raw_inverse:
            continue
        eid = resolution.canonical(str(fm["id"])) or str(fm["id"])
        superseder = resolution.canonical(raw_inverse)
        if superseder is None:
            continue        # a DANGLING inverse -- `check_resolution` owns that one; not this check
        if (superseder, eid) not in admitted:
            # SAME SHAPE as the other three outcomes -- {id, superseder, reason}. `SupersessionError`
            # formats a blocking list uniformly, so a fourth outcome with a bespoke key name would
            # KeyError inside the raise: the failure path would fail.
            unbacked_inverses.append({
                "id": eid, "superseder": superseder,
                "reason": "authored superseded_by has no canonical sci:supersedes edge behind it",
            })
        superseded_by_id[eid] = superseder      # canonicalized, so reconciliation compares like-for-like
```

```python
# consolidation.py -- mark_superseded. The inverse is written alongside the status. Without it the
# tool emits a `superseded` record with no lineage and no basis -- which Task 10's boundary rejects.
# The tool would have been the first thing to violate its own contract.
#
# THE INVERSE IS A PROJECTION, SO IT MUST RECONCILE, NOT JUST INITIALIZE. `status == superseded`
# currently short-circuits the whole member, conflating "the status is already right" with "the
# projection is already right" -- so a MISSING or STALE `superseded_by` stays broken forever and no
# re-run repairs it. A derived field is reconciled every pass, or it is not derived.
#
# `to_mark`/`applied` KEEP THEIR MEANING (status stamping, already-superseded excluded); repairs get
# their OWN fields. See the report-contract box below.
    entries = iter_entity_frontmatter(project_root)
    graph = build_supersedes_graph(entries, resolution=_id_resolution(project_root, entries))

    for chain in graph.linear:
        for member in chain.superseded:
            superseder = graph.superseder_by_id[member]
            if not _supports_superseded(graph.kind_by_id[member]):
                skipped_kinds.append({"id": member, "kind": graph.kind_by_id[member]})
                continue
            if graph.status_by_id.get(member) != _SUPERSEDED:
                to_mark.append(member)                                    # status not yet stamped
            elif graph.superseded_by_id.get(member) != superseder:
                to_repair.append(member)                                  # status fine, inverse STALE
            # else: fully reconciled -- touch nothing.

    # THE ADMISSION OUTCOMES COME OFF THE GRAPH -- they are not recomputed here, and `mismatched` is
    # NOT a local name in this function (an earlier draft read it as though it were, which is a
    # NameError at best and a second, divergent classification at worst). The builder decided; this
    # function reports what it decided.
    report["mismatched_kinds"] = [dict(m) for m in graph.mismatched]
    report["unresolved_targets"] = [dict(u) for u in graph.unresolved_targets]
    report["archived_targets"] = [dict(a) for a in graph.archived_targets]
    report["unmanaged_targets"] = [dict(u) for u in graph.unmanaged_targets]
    report["unbacked_inverses"] = [dict(u) for u in graph.unbacked_inverses]
    report["to_repair"] = list(to_repair)

    if apply:
        # ALL-OR-NONE, PHASE 1: the authored graph must BE a graph, and the corpus must not contradict
        # it. `archived_targets` and `unmanaged_targets` are NOT here -- both are edges the graph
        # resolves fine and that we simply have no local markdown file to stamp.
        # `unbacked_inverses` IS: a record claiming a superseder the graph does not contain means the
        # corpus disagrees with itself about what supersedes what, and every projection derived from
        # it is suspect. Reconciliation cannot silently "fix" it either -- there is no edge to
        # reconcile TOWARD, so the only honest moves are refuse, and report.
        blocking = [*graph.mismatched, *graph.unresolved_targets, *graph.unbacked_inverses]
        if blocking:
            raise SupersessionError(blocking)

        # ALL-OR-NONE, PHASE 2: PREPARE EVERY WRITE BEFORE COMMITTING ANY OF THEM. Task 10 puts
        # schema + resolution validation on the write boundary, and a member can fail it for reasons
        # this function never looked at -- an unrelated invalid field already on the record. With a
        # sequential write-and-validate loop, member 1 lands on disk and member 2 raises, leaving a
        # corpus that is neither the old state nor the new one -- while this box promised otherwise.
        # `_prepare_write` renders and validates and writes NOTHING, so every rejection lands
        # before the first byte does.
        prepared = [_prepare_supersession(project_root, graph, m) for m in to_mark + to_repair]
        for write in prepared:                    # validation is BEHIND us; this loop only commits
            _commit_write(write)

        report["applied"] = list(to_mark)
        report["repaired"] = list(to_repair)
```

> #### What "all-or-none" promises — and what it does not
>
> It promises exactly this: **no `superseded` write is committed if any planned write would be
> rejected.** Graph-admission errors (mismatched pairs, unresolved targets) are refused before
> anything is prepared; per-record schema/resolution failures are refused before anything is
> committed. There is no input, valid or invalid, for which this operation writes *some* of its
> planned records and then raises.
>
> It does **not** promise atomicity against a process kill or an I/O error partway through the commit
> loop. Individual writes are atomic (`_atomic_replace_text`), the loop is not, and claiming
> otherwise would need a corpus-wide transaction we do not have. **What makes that survivable is the
> reconciliation this task adds**: the operation is idempotent and it *repairs* — a re-run recomputes
> the graph, sees the members whose projection is missing or stale, and finishes the job. A crash
> leaves a corpus that the next run converges; it does not leave one that no run will ever touch
> again, which is precisely what rev 1's status-only short-circuit did.
>
> Stating the boundary is the point. An unqualified "all-or-none" over a non-transactional loop is a
> claim the code cannot keep, and a promise the reader will rely on.

`SupersedesGraph` gains `superseder_by_id` (the **derived** inverse, from the admitted edges),
`superseded_by_id` (the **authored** `superseded_by` per id, read in the same frontmatter pass as
`status_by_id`, so a stale inverse is visible without a second scan), and the three edge-admission
outcomes: `mismatched`, `archived_targets`, `unresolved_targets`. `build_supersedes_graph` takes
`archived` as an argument rather than reading the index itself — the builder stays a pure function of
its inputs, which is what lets every test above construct one without an archive on disk.

> #### The report is a PUBLIC contract — extend it, do not redefine it
>
> `to_mark` and `applied` mean one thing today and are documented saying so
> (`consolidation.py:199-207`): *member ids a linear chain would stamp `superseded`* — **explicitly
> excluding already-superseded members** — and they are serialized to JSON by
> `entities_mark_superseded_command`. Widening them to also mean "status unchanged, projection
> repaired" would silently change what an existing key means for every consumer that already reads
> it, with no version and no signal. **A field whose meaning changes under a consumer is worse than
> a field that disappears** — the disappearance is at least loud.
>
> So repairs get **`to_repair` / `repaired`**, and the two existing keys keep their exact meanings.
> `report["skipped_kinds"]` is unchanged. **`mismatched_kinds`, `unresolved_targets`,
> `archived_targets`, `unmanaged_targets`, and `unbacked_inverses` are new**, and each is its own key
> precisely because they carry different obligations — three refuse-and-block, two refuse-but-proceed.
> Folding them into a single "problems" list would put an ordinary archived lineage next to a dangling
> edge and make a consumer guess which one stops a release. All seven additions are additive; nothing
> existing changes meaning.

- [x] **Step 5b: Test the operation on a kind that is supersedable TODAY — `interpretation`.**

> **`mark_superseded` cannot stamp a `hypothesis` in this task, and a test that says otherwise is
> not a test.** `_supports_superseded` consults `_STATUS_VALUES` (`consolidation.py:64-74`), and
> `_STATUS_VALUES["hypothesis"]` today is `{proposed, under-investigation, partially-supported,
> supported, weakened, refuted, archived}` — **no `superseded`**. So the member is routed to
> `skipped_kinds`, nothing is written, and `edit_entity`'s `_validate_status` (`entities.py:952`)
> would reject the status anyway. Hypothesis becomes stampable in **Task 8**, with the descriptor.
>
> An earlier draft put hypothesis apply-tests here. They could not have passed — and worse, the
> *reason* they'd fail (`to_mark == []`) is silent: `mark_superseded` returns a clean report,
> `apply=True` writes nothing, and an assertion on `report["applied"]` would have been the only
> thing standing between us and a green suite over an operation that did nothing.
>
> **So Phase 2 stays meaning-neutral.** Leg 3 is a **generic** change — the inverse, the kind-pair
> refusal, the reconciliation — and it is tested here on `interpretation`, which declares
> `superseded` *and* is an admitted `sci:supersedes` endpoint today. The **hypothesis-specific**
> apply tests (two-node, three-node, schema-closure) move to **Task 8**, beside the descriptor
> change that makes them executable. *A test belongs in the task where its subject exists.*

```python
# science/tests/test_consolidation_mark_superseded.py  -- all on `interpretation`, all green TODAY.
#
# THE FIXTURE HELPERS. Earlier drafts used all of these without defining any of them.

def _supersedes(target: str) -> dict[str, str]:
    """One canonical supersession edge, in the ONLY spelling the toolkit reads."""
    return {"predicate": "sci:supersedes", "target": target}


def _write(tmp_path: Path, subdir: str, slug: str, fm: dict) -> Path:
    """Write one entity markdown file under `entities/<subdir>/<slug>.md`."""
    path = tmp_path / "entities" / subdir / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{yaml.safe_dump(fm, sort_keys=False)}---\n\nbody\n", encoding="utf-8")
    return path


def _relate(tmp_path: Path, slug: str, *, supersedes: str) -> None:
    """Append a canonical supersedes edge to an entity written by `_write`."""
    path = next(tmp_path.glob(f"entities/*/{slug}.md"))
    fm = read_frontmatter(path)
    fm.setdefault("relations", []).append(_supersedes(supersedes))
    _write(tmp_path, path.parent.name, slug, fm)


def _manual_alias(tmp_path: Path, alias: str, canonical: str) -> None:
    """Register a project manual alias -- `knowledge/sources/<profile>/mappings.yaml`
    (`commons/aliases.py:11-23`), which `load_project_sources` folds into the resolver.

    `build_alias_map` registers the mapping UNCONDITIONALLY (`sources.py:660-662`), so this is how a
    reference RESOLVES to an id that NO RECORD BACKS -- which is a dangling edge, not an unmanaged
    one. (For a target that resolves AND is backed but is not ours to stamp -- the commons overlay,
    a non-markdown source -- construct the `IdResolution` directly; see `_resolution`.)
    """
    path = tmp_path / "knowledge" / "sources" / "local" / "mappings.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    aliases = (existing or {}).get("aliases", {})
    aliases[alias] = canonical
    path.write_text(yaml.safe_dump({"aliases": aliases}, sort_keys=False), encoding="utf-8")


def _archive(tmp_path: Path, subdir: str, slug: str, fm: dict) -> None:
    """Write an entity and archive it THROUGH THE REAL OP -- never by hand-building the index.

    `archive_entities` selects by status, relocates the file under `entities/_archive/`, and appends
    the index row (`archive.py:213`). A hand-written `_archive/` file with no index row, or an index
    row with no file, is a state the tool cannot produce -- and a fixture that fabricates one tests
    the fixture. The status must be archivable (`superseded`/`archived`), which is exactly the state
    a real superseded-then-archived record is in.
    """
    from science_tool.archive import archive_entities
    _write(tmp_path, subdir, slug, fm)
    archive_entities(tmp_path, apply=True)

def test_the_stamped_record_CARRIES_its_lineage(tmp_path: Path) -> None:
    # Rev 1 wrote `status` alone, so the toolkit's own supersession produced a record with no
    # lineage and no basis -- which Task 10's boundary refuses. A tool that cannot satisfy the
    # schema it enforces has not implemented supersession; it has renamed it.
    _write(tmp_path, "interpretations", "i-v1", {"id": "interpretation:i-v1",
                                                 "kind": "interpretation", "status": "active"})
    _write(tmp_path, "interpretations", "i-v2", {"id": "interpretation:i-v2",
                                                 "kind": "interpretation",
                                                 "relations": [_supersedes("interpretation:i-v1")]})

    mark_superseded(tmp_path, apply=True)
    fm = read_frontmatter(tmp_path / "entities/interpretations/i-v1.md")

    assert fm["status"] == "superseded"
    assert fm["superseded_by"] == "interpretation:i-v2"


def test_a_CHAIN_records_the_immediate_superseder_not_the_survivor(tmp_path: Path) -> None:
    # A -> B -> C. The survivor is A, but the edge that closed C was authored by B. `superseded_by`
    # INVERTS the authored edge; it does not summarize the chain. Stamping A onto C would discard
    # B's supersession entirely -- and the two-node test above cannot tell the difference, which is
    # the only reason this one exists.
    for n in ("i-v1", "i-v2", "i-v3"):
        _write(tmp_path, "interpretations", n, {"id": f"interpretation:{n}",
                                                "kind": "interpretation", "status": "active"})
    _relate(tmp_path, "i-v2", supersedes="interpretation:i-v1")
    _relate(tmp_path, "i-v3", supersedes="interpretation:i-v2")

    mark_superseded(tmp_path, apply=True)

    v1 = read_frontmatter(tmp_path / "entities/interpretations/i-v1.md")
    v2 = read_frontmatter(tmp_path / "entities/interpretations/i-v2.md")
    assert v1["superseded_by"] == "interpretation:i-v2"      # NOT i-v3, the survivor
    assert v2["superseded_by"] == "interpretation:i-v3"
    assert "superseded_by" not in read_frontmatter(tmp_path / "entities/interpretations/i-v3.md")


def test_an_ILLEGAL_kind_pair_is_REFUSED_not_written(tmp_path: Path) -> None:
    # `workflow-run -> interpretation` is not an allowed `sci:supersedes` pair (`core.py:687-701`:
    # workflow-run x workflow-run, and conclusion x conclusion -- never across). `materialize`
    # rejects the edge, but THIS path never calls materialize, so nothing stopped the topology scan
    # from stamping `superseded_by: workflow-run:...` onto an interpretation.
    _write(tmp_path, "interpretations", "i-v1", {"id": "interpretation:i-v1",
                                                 "kind": "interpretation", "status": "active"})
    _write(tmp_path, "workflow-runs", "wr-1", {"id": "workflow-run:wr-1", "kind": "workflow-run",
                                               "relations": [_supersedes("interpretation:i-v1")]})

    report = mark_superseded(tmp_path, apply=False)

    assert report["to_mark"] == []
    assert report["mismatched_kinds"] == [
        {"id": "interpretation:i-v1", "superseder": "workflow-run:wr-1",
         "reason": "workflow-run -> interpretation is not an allowed sci:supersedes pair"},
    ]
    with pytest.raises(SupersessionError):        # ALL-OR-NONE: apply refuses outright
        mark_superseded(tmp_path, apply=True)
    fm = read_frontmatter(tmp_path / "entities/interpretations/i-v1.md")
    assert fm["status"] == "active" and "superseded_by" not in fm      # UNTOUCHED


def test_an_ILLEGAL_edge_does_not_SUPPRESS_a_legal_chain(tmp_path: Path) -> None:
    # THE ORDERING TEST -- and the reason the pair rule lives in the BUILDER, not in the apply loop.
    #
    # An illegal edge is still an EDGE: it joins the component and counts toward in-degree. With the
    # check inside the `graph.linear` loop, `_classify` sees in_deg[i-v1] == 2, calls the component
    # NON-LINEAR, and it never reaches that loop at all. So `mismatched_kinds` comes back EMPTY --
    # the guard never runs -- AND the legal `i-v2 -> i-v1` supersession is silently suppressed,
    # misfiled as "branched or cyclic" when nothing branched: one of its edges was not a
    # supersession. A guard downstream of the corruption it detects is not a guard.
    _write(tmp_path, "interpretations", "i-v1", {"id": "interpretation:i-v1",
                                                 "kind": "interpretation", "status": "active"})
    _write(tmp_path, "interpretations", "i-v2", {"id": "interpretation:i-v2",
                                                 "kind": "interpretation",
                                                 "relations": [_supersedes("interpretation:i-v1")]})
    _write(tmp_path, "workflow-runs", "wr-1", {"id": "workflow-run:wr-1", "kind": "workflow-run",
                                               "relations": [_supersedes("interpretation:i-v1")]})

    report = mark_superseded(tmp_path, apply=False)

    # The illegal edge is REPORTED, not absorbed...
    assert [m["superseder"] for m in report["mismatched_kinds"]] == ["workflow-run:wr-1"]
    # ...and dropping it leaves a chain that is perfectly linear.
    assert report["non_linear"] == []
    assert report["chains"] == [{"survivor": "interpretation:i-v2",
                                 "members": ["interpretation:i-v1"], "linear": True}]
    assert report["to_mark"] == ["interpretation:i-v1"]


def test_a_mixed_corpus_writes_NOTHING_on_apply(tmp_path: Path) -> None:
    # THE ALL-OR-NONE REGRESSION -- and it is a separate test from the one above ON PURPOSE.
    #
    # The dry-run test proves the illegal edge is REPORTED and the legal chain SURVIVES. It says
    # nothing about apply, because it never calls it. So the property the box actually promises --
    # "any blocking error and apply writes NOTHING, not the unaffected components either" -- was
    # asserted in prose and tested nowhere. An implementation that raises AFTER stamping i-v1 (the
    # legal, unaffected member) passes every other test in this file.
    #
    # It asserts the BYTES of the legal target, not the report: the report is what the operation says
    # it did.
    _write(tmp_path, "interpretations", "i-v1", {"id": "interpretation:i-v1",
                                                 "kind": "interpretation", "status": "active"})
    _write(tmp_path, "interpretations", "i-v2", {"id": "interpretation:i-v2",
                                                 "kind": "interpretation",
                                                 "relations": [_supersedes("interpretation:i-v1")]})
    _write(tmp_path, "interpretations", "i-w1", {"id": "interpretation:i-w1",
                                                 "kind": "interpretation", "status": "active"})
    _write(tmp_path, "workflow-runs", "wr-1", {"id": "workflow-run:wr-1", "kind": "workflow-run",
                                               "relations": [_supersedes("interpretation:i-w1")]})
    legal = tmp_path / "entities/interpretations/i-v1.md"
    before = legal.read_bytes()

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)

    # i-v1's supersession is legal, linear, and would have been stamped. It is NOT stamped, because
    # ANOTHER component's edge is invalid. Corpus-wide derivation from a corpus that is not a graph.
    assert legal.read_bytes() == before


def test_an_ARCHIVED_target_is_a_VALID_edge_with_no_live_mutation(tmp_path: Path) -> None:
    # THE MIDDLE STATE. Superseding a record and later archiving it is the normal end of a lineage:
    # the canonical edge is TRUE, the record exists, and it is frozen. `iter_entity_frontmatter` does
    # not scan `_archive/`, so before this task the edge was indistinguishable from a typo and was
    # dropped in silence.
    #
    # It REPORTS and it does NOT BLOCK: an ordinary historical lineage must not stop an unrelated
    # supersession from applying.
    _archive(tmp_path, "interpretations", "i-old", {"id": "interpretation:i-old",
                                                    "kind": "interpretation",
                                                    "status": "superseded"})
    _write(tmp_path, "interpretations", "i-new", {"id": "interpretation:i-new",
                                                  "kind": "interpretation",
                                                  "relations": [_supersedes("interpretation:i-old")]})
    _write(tmp_path, "interpretations", "j-v1", {"id": "interpretation:j-v1",
                                                 "kind": "interpretation", "status": "active"})
    _write(tmp_path, "interpretations", "j-v2", {"id": "interpretation:j-v2",
                                                 "kind": "interpretation",
                                                 "relations": [_supersedes("interpretation:j-v1")]})

    report = mark_superseded(tmp_path, apply=True)       # does NOT raise

    assert report["archived_targets"] == [
        {"id": "interpretation:i-old", "superseder": "interpretation:i-new",
         "reason": "target is archived (frozen); no live record to stamp"},
    ]
    assert report["unresolved_targets"] == []
    # The archived target is not a chain member and is never stamped...
    assert report["chains"] == [{"survivor": "interpretation:j-v2",
                                 "members": ["interpretation:j-v1"], "linear": True}]
    # ...and the unrelated live chain applies normally. An archived edge is not an error.
    assert report["applied"] == ["interpretation:j-v1"]


def test_an_UNRESOLVED_target_is_REPORTED_and_BLOCKS_apply(tmp_path: Path) -> None:
    # THE THIRD STATE, and the one the old `if dst not in known: continue` erased. A canonical
    # supersession edge pointing at an id that exists NOWHERE -- not live, not archived -- is a
    # dangling authored relation. The old filter made "a derived inverse can never dangle" true by
    # DELETING the counterexample: no edge, no chain, no finding, clean report, green apply.
    #
    # It blocks apply for the same reason a mismatched pair does: the derivation is corpus-wide, and
    # part of this corpus is not a graph.
    _write(tmp_path, "interpretations", "i-v1", {"id": "interpretation:i-v1",
                                                 "kind": "interpretation", "status": "active"})
    _write(tmp_path, "interpretations", "i-v2", {"id": "interpretation:i-v2",
                                                 "kind": "interpretation",
                                                 "relations": [_supersedes("interpretation:i-v1"),
                                                               _supersedes("interpretation:i-GONE")]})
    target = tmp_path / "entities/interpretations/i-v1.md"
    before = target.read_bytes()

    report = mark_superseded(tmp_path, apply=False)

    assert report["unresolved_targets"] == [
        {"id": "interpretation:i-GONE", "superseder": "interpretation:i-v2",
         "reason": "sci:supersedes target resolves to nothing"},
    ]
    assert report["archived_targets"] == []
    # Report mode still enumerates EVERYTHING -- the legal chain is fully diagnosed alongside it.
    assert report["to_mark"] == ["interpretation:i-v1"]

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)
    assert target.read_bytes() == before          # all-or-none, again


def test_a_LIVE_ALIAS_target_RESOLVES_and_is_not_called_unresolved(tmp_path: Path) -> None:
    # THE FALSE-POSITIVE GUARD, and it is the one that would have BROKEN WORKING PROJECTS.
    #
    # `materialize` resolves relation targets through a ReferenceResolver built over live
    # `aliases`/`same_as` (sources.py:610-626, materialize.py:1619-1627). A supersedes edge authored
    # against an alias therefore materializes perfectly today. A builder that answers "live? archived?
    # nowhere?" by RAW STRING MEMBERSHIP calls that same edge `unresolved` -- and `unresolved` BLOCKS
    # apply. Trading a silent drop for a false refusal is not a fix.
    _write(tmp_path, "interpretations", "i-v1", {"id": "interpretation:i-v1",
                                                 "kind": "interpretation", "status": "active",
                                                 "aliases": ["interpretation:old-name"]})
    _write(tmp_path, "interpretations", "i-v2", {"id": "interpretation:i-v2",
                                                 "kind": "interpretation",
                                                 # authored against the ALIAS, not the canonical id
                                                 "relations": [_supersedes("interpretation:old-name")]})

    report = mark_superseded(tmp_path, apply=True)

    assert report["unresolved_targets"] == []          # NOT a dangling edge
    assert report["applied"] == ["interpretation:i-v1"]   # canonicalized, then stamped
    fm = read_frontmatter(tmp_path / "entities/interpretations/i-v1.md")
    assert fm["superseded_by"] == "interpretation:i-v2"


def test_an_ARCHIVED_ALIAS_target_resolves_to_the_ARCHIVE_not_to_nowhere(tmp_path: Path) -> None:
    # Same trap, other population. `ArchiveIndex.resolvable_ids()` maps every archived alias/same_as
    # token to its canonical id (archive.py:51-58), and `load_project_sources` folds exactly that map
    # into the resolver (sources.py:619-626) -- which is why an alias of an ARCHIVED entity resolves
    # in the graph. `active_by_id` is canonical-only and does not, which is precisely the draft that
    # would have reported this edge `unresolved` and refused to apply.
    _archive(tmp_path, "interpretations", "i-old", {"id": "interpretation:i-old",
                                                    "kind": "interpretation", "status": "superseded",
                                                    "aliases": ["interpretation:i-ancient"]})
    _write(tmp_path, "interpretations", "i-new", {"id": "interpretation:i-new",
                                                  "kind": "interpretation",
                                                  "relations": [_supersedes("interpretation:i-ancient")]})

    report = mark_superseded(tmp_path, apply=True)      # does NOT raise

    assert report["unresolved_targets"] == []
    assert report["archived_targets"] == [
        {"id": "interpretation:i-old", "superseder": "interpretation:i-new",   # CANONICAL, not the alias
         "reason": "target is archived (frozen); no live record to stamp"},
    ]


def _resolution(*, mutable: set[str], archived: set[str], kinds: dict[str, str]) -> IdResolution:
    """Construct the resolution bundle DIRECTLY. The builder is a pure function of its inputs -- that
    is the whole reason it takes an `IdResolution` -- so the commons/non-markdown populations, which
    would otherwise need a commons repo on disk, are expressible as the data they actually are."""
    entities = [Entity(canonical_id=cid, kind=kind, title=cid) for cid, kind in kinds.items()]
    return IdResolution(resolver=ReferenceResolver.from_entities(entities),
                        mutable=frozenset(mutable), archived=frozenset(archived), kind_by_id=kinds)


def test_a_RESOLVABLE_LEGAL_target_WE_DO_NOT_OWN_is_reported_and_does_not_BLOCK() -> None:
    # THE SIXTH ROW. An earlier draft's `else` swallowed this one: it classified with
    # `if dst not in live: -> archived`, on the theory that "an id cannot resolve to neither." It can --
    # the commons overlay and non-markdown sources put ids into the resolver that are in NEITHER the
    # live markdown scan NOR the archive index -- and that draft would have filed this target as a
    # frozen archived record, then indexed `kind_by_id[dst]` for a key that was never there.
    #
    # RESOLVABLE, LEGAL, and OURS are three questions. Resolvable-and-legal but not ours -> nothing to
    # stamp -> report, and do not block. NOTE the target is a `conclusion`, not a `dataset`: an
    # unmanaged target must still be a LEGAL endpoint to land here. The illegal one is the next test.
    entries = [
        (Path("i-v2.md"), {"id": "interpretation:i-v2", "kind": "interpretation",
                           "relations": [_supersedes("conclusion:commons-thing")]}),
        (Path("j-v1.md"), {"id": "interpretation:j-v1", "kind": "interpretation", "status": "active"}),
        (Path("j-v2.md"), {"id": "interpretation:j-v2", "kind": "interpretation",
                           "relations": [_supersedes("interpretation:j-v1")]}),
    ]
    graph = build_supersedes_graph(entries, _resolution(
        mutable={"interpretation:i-v2", "interpretation:j-v1", "interpretation:j-v2"},
        archived=set(),
        kinds={"interpretation:i-v2": "interpretation", "interpretation:j-v1": "interpretation",
               "interpretation:j-v2": "interpretation",
               "conclusion:commons-thing": "conclusion"},   # backed by a source; not live markdown
    ))

    assert graph.unresolved_targets == ()                  # it RESOLVES
    assert graph.archived_targets == ()                    # ...and it is NOT archived
    assert graph.mismatched == ()                          # ...and the pair is LEGAL
    assert [u["id"] for u in graph.unmanaged_targets] == ["conclusion:commons-thing"]
    assert graph.linear == (SupersededChain(survivor="interpretation:j-v2",
                                            superseded=("interpretation:j-v1",)),)


def test_an_ILLEGAL_pair_into_an_UNMANAGED_target_is_MISMATCHED_not_benign() -> None:
    # THE ORDERING BUG, stated as a corpus. `dataset` is not an endpoint of `supersedes` at ANY
    # position (core.py:687 -- `allowed_kind_pairs` is workflow-run + the conclusion pairs), so
    # `materialize` RAISES on this edge. But the draft that answered OWNERSHIP first saw "resolves,
    # not mutable" and `continue`d into `unmanaged_targets` -- benign, unstampable, apply proceeds --
    # WITHOUT EVER REACHING `relation_allows_kinds`. The pair check sat downstream of the corruption
    # it was written to detect, which is the same defect this task already fixed one layer up (the
    # kind guard inside `graph.linear`).
    entries = [(Path("i.md"), {"id": "interpretation:new", "kind": "interpretation",
                               "relations": [_supersedes("dataset:commons-thing")]})]
    graph = build_supersedes_graph(entries, _resolution(
        mutable={"interpretation:new"}, archived=set(),
        kinds={"interpretation:new": "interpretation", "dataset:commons-thing": "dataset"},
    ))

    assert graph.unmanaged_targets == ()                   # NOT waved through as benign debt
    assert [m["id"] for m in graph.mismatched] == ["dataset:commons-thing"]
    assert "interpretation -> dataset" in graph.mismatched[0]["reason"]


def test_an_ILLEGAL_pair_into_the_ARCHIVE_is_MISMATCHED_not_benign(tmp_path: Path) -> None:
    # Same bug, other population, and end-to-end: an archived row carries a KIND (`archive.py:32`), so
    # the pair is answerable -- and it is wrong. "We won't stamp it" was never a licence to skip the
    # edge's own validity. It BLOCKS, exactly as a live illegal pair does.
    _archive(tmp_path, "datasets", "d-old", {"id": "dataset:d-old", "kind": "dataset",
                                             "status": "archived"})
    _write(tmp_path, "interpretations", "i-new", {"id": "interpretation:i-new",
                                                  "kind": "interpretation",
                                                  "relations": [_supersedes("dataset:d-old")]})

    report = mark_superseded(tmp_path, apply=False)

    assert report["archived_targets"] == []                # NOT filed as a benign historical edge
    assert [m["id"] for m in report["mismatched_kinds"]] == ["dataset:d-old"]

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)


def test_an_ARCHIVE_ROW_WITH_NO_KIND_is_refused_EXACTLY_AS_MATERIALIZE_refuses_it(tmp_path: Path) -> None:
    # `ArchiveRow.kind` is nullable (`archive.py:32`) -- an archive row written before the field
    # existed carries none. Materialize turns that into `_ArchivedEndpoint(kind=arow.kind or "")`
    # (`materialize.py:1626`), and because `supersedes` declares `allowed_kind_pairs` -- an
    # authoritative allow-list -- `""` matches NO pair, so materialize RAISES on the edge.
    #
    # A draft here derived the kind from the ID PREFIX instead, which would have read `interpretation`
    # off `interpretation:i-old` and ADMITTED the edge: consolidation stamps the file, and the graph
    # then refuses to build. A write that succeeds and leaves the corpus unmaterializable is worse
    # than either authority refusing alone. So this mirrors `or ""` verbatim, and the row BLOCKS.
    _archive(tmp_path, "interpretations", "i-old", {"id": "interpretation:i-old",
                                                    "status": "superseded"})   # NO `kind`
    _write(tmp_path, "interpretations", "i-new", {"id": "interpretation:i-new",
                                                  "kind": "interpretation",
                                                  "relations": [_supersedes("interpretation:i-old")]})

    report = mark_superseded(tmp_path, apply=False)

    assert report["archived_targets"] == []       # NOT waved through as a benign historical edge
    assert [m["id"] for m in report["mismatched_kinds"]] == ["interpretation:i-old"]
    assert "(no kind)" in report["mismatched_kinds"][0]["reason"]

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)


def test_an_ALIAS_to_an_id_NOTHING_BACKS_is_DANGLING_and_BLOCKS(tmp_path: Path) -> None:
    # ROW 2, and the trap in the fixture that used to "prove" the unmanaged case. `build_alias_map`
    # registers a manual alias UNCONDITIONALLY (`sources.py:660-662`), so this token RESOLVES -- to an
    # id that no live entity, no archive row, and no source record backs. The draft that keyed
    # ownership off `mutable`/`archived` alone would have called that `unmanaged`: benign, no block.
    #
    # But with no record there is no KIND, and with no kind the legality question is UNANSWERABLE. An
    # unanswerable guard must not report "benign". This is a dangling edge with extra steps, and it
    # blocks like one.
    _write(tmp_path, "interpretations", "i-v2", {"id": "interpretation:i-v2",
                                                 "kind": "interpretation",
                                                 "relations": [_supersedes("interpretation:ghost")]})
    _manual_alias(tmp_path, "interpretation:ghost", "interpretation:ghost-canonical")

    report = mark_superseded(tmp_path, apply=False)

    assert report["unmanaged_targets"] == []               # NOT benign debt
    assert [u["id"] for u in report["unresolved_targets"]] == ["interpretation:ghost-canonical"]
    assert "no live, archived, or source record backs" in report["unresolved_targets"][0]["reason"]

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)


def test_a_RESOLVABLE_but_GROUNDLESS_inverse_is_REPORTED_and_BLOCKS_apply(tmp_path: Path) -> None:
    # THE FOURTH OUTCOME -- the one every other net in this plan misses.
    #
    # `i-v1.superseded_by = i-v2`, and i-v2 EXISTS. But nobody authored `i-v2 sci:supersedes i-v1`.
    # Schema passes (non-empty string, discharges the `superseded` anyOf). `check_resolution` passes
    # (the id RESOLVES -- it only ever caught DANGLING refs, and an earlier revision claimed it caught
    # this one too). Reconciliation never looks (i-v1 is in no chain, because there is no edge). The
    # write boundary never sees it (nothing can hand a groundless inverse to a writer any more).
    #
    # Four nets, zero coverage -- for the exact failure `supersedes:` was deleted to prevent: a
    # lineage that is true and grounded in nothing.
    _write(tmp_path, "interpretations", "i-v1", {"id": "interpretation:i-v1",
                                                 "kind": "interpretation", "status": "superseded",
                                                 "superseded_by": "interpretation:i-v2"})
    _write(tmp_path, "interpretations", "i-v2", {"id": "interpretation:i-v2",
                                                 "kind": "interpretation", "status": "active"})
    target = tmp_path / "entities/interpretations/i-v1.md"
    before = target.read_bytes()

    report = mark_superseded(tmp_path, apply=False)

    assert report["unresolved_targets"] == []     # it RESOLVES. That is the whole point.
    assert report["unbacked_inverses"] == [
        {"id": "interpretation:i-v1", "superseder": "interpretation:i-v2",
         "reason": "authored superseded_by has no canonical sci:supersedes edge behind it"},
    ]

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)
    assert target.read_bytes() == before          # blocks, and does not silently "repair" it either


def test_a_NON_LINEAR_member_is_BACKED_even_though_it_is_never_stamped(tmp_path: Path) -> None:
    # THE CONTROL for the test above, and the reason `unbacked` is computed against `edges` rather
    # than `superseder_by_id`. A member of a BRANCHED component has a real in-edge -- it is grounded --
    # but it is never stamped, because the survivor is ambiguous. `superseder_by_id` covers LINEAR
    # chains only, so comparing against it would report every non-linear member as unbacked and block
    # apply on a corpus whose only sin is a branch the tool already handles by skipping it.
    _write(tmp_path, "interpretations", "i-v1", {"id": "interpretation:i-v1",
                                                 "kind": "interpretation", "status": "superseded",
                                                 "superseded_by": "interpretation:i-a"})
    for n in ("i-a", "i-b"):     # TWO supersedors -> branched -> non-linear
        _write(tmp_path, "interpretations", n, {"id": f"interpretation:{n}",
                                                "kind": "interpretation",
                                                "relations": [_supersedes("interpretation:i-v1")]})

    report = mark_superseded(tmp_path, apply=True)      # does NOT raise

    assert report["unbacked_inverses"] == []            # the edge i-a -> i-v1 was ADMITTED
    assert len(report["non_linear"]) == 1               # ...and the component is still skipped
    assert report["applied"] == []


def test_a_STALE_inverse_is_REPAIRED(tmp_path: Path) -> None:
    # The status is already `superseded`, so rev 1 `continue`d -- conflating "the status is right"
    # with "the projection is right". A record whose `superseded_by` is missing or points at the
    # WRONG entity is then invalid forever and no re-run touches it. `test_report_skips_already_
    # superseded_members` pins exactly that behaviour today, and it is amended by this task: the
    # status alone no longer discharges the member. A derived field is reconciled every pass.
    _write(tmp_path, "interpretations", "i-v1", {"id": "interpretation:i-v1",
                                                 "kind": "interpretation", "status": "superseded",
                                                 "superseded_by": "interpretation:i-WRONG"})
    _write(tmp_path, "interpretations", "i-v2", {"id": "interpretation:i-v2",
                                                 "kind": "interpretation",
                                                 "relations": [_supersedes("interpretation:i-v1")]})

    report = mark_superseded(tmp_path, apply=True)

    # `repaired`, NOT `applied`. The status was already correct; only the projection moved. Reusing
    # `applied` would silently redefine a documented, JSON-serialized key (`consolidation.py:199`)
    # for every consumer already reading it -- and a key whose MEANING changes under a consumer is
    # worse than one that disappears, because the disappearance is at least loud.
    assert report["applied"] == []
    assert report["repaired"] == ["interpretation:i-v1"]
    fm = read_frontmatter(tmp_path / "entities/interpretations/i-v1.md")
    assert fm["superseded_by"] == "interpretation:i-v2"


def test_a_RECONCILED_record_is_BYTE_IDENTICAL_afterwards(tmp_path: Path) -> None:
    # THE IDEMPOTENCE CONTROL -- and it asserts the FILE, not the report.
    #
    # An earlier draft asserted only `to_mark == [] and applied == []`. That passes for an
    # implementation that rewrites the file and merely forgets to append to the report -- which is
    # the more likely bug of the two, and the one with consequences: `edit_entity` stamps `updated:`
    # unconditionally, so a re-stamping no-op churns `updated:` across every superseded record in
    # the corpus and makes a re-run indistinguishable from a real migration in `git diff`. The
    # report is what the operation SAYS it did. The bytes are what it did.
    _write(tmp_path, "interpretations", "i-v1", {"id": "interpretation:i-v1",
                                                 "kind": "interpretation", "status": "superseded",
                                                 "superseded_by": "interpretation:i-v2"})
    _write(tmp_path, "interpretations", "i-v2", {"id": "interpretation:i-v2",
                                                 "kind": "interpretation",
                                                 "relations": [_supersedes("interpretation:i-v1")]})
    target = tmp_path / "entities/interpretations/i-v1.md"
    before = target.read_bytes()

    report = mark_superseded(tmp_path, apply=True)

    assert target.read_bytes() == before          # NOT ONE BYTE -- `updated:` included
    assert report["to_mark"] == [] and report["applied"] == [] and report["repaired"] == []
```

- [x] **Step 5c: Amend `test_report_skips_already_superseded_members`.** It pins the *old* meaning
  of "already superseded" — status-only — and this task splits that into two facts. Its fixture has
  no `superseded_by`, so under the new rule the member **needs the inverse** and is correctly
  marked. Rewrite it to assert the reconciliation, and keep a `to_mark == []` case for the
  fully-reconciled record (above). **Do not delete it** — it is the regression that proves the skip
  still exists for records that need nothing.

- [x] **Step 5d: Surface what BLOCKS in `validate` — all of it, not just the fourth outcome.**
  `mark_superseded` blocks on an unbacked inverse, but it is an *opt-in* command — a corpus can carry
  a groundless lineage indefinitely without anyone running it. `validate` is the pass everyone runs.

  > ### ⚠️ RULING 8 — this step's original scope was the gap. Found by review, again.
  >
  > *Named only the unbacked inverse, so that is all the shipped check emitted — while the builder was
  > by then recording **three** blocking outcomes. `runner.run` over `i sci:supersedes i` and over
  > `i sci:supersedes dataset:d` produced **zero** relevant findings, although `materialize` refuses
  > to build a graph over either and `mark_superseded --apply` blocks both. The module's own rationale
  > — "the operation is opt-in, validation is universal" — argued for exactly the coverage it did not
  > have.*
  >
  > **Two severity tiers, on two different axes, and conflating them is the status-vocabulary incident
  > repeating:**
  >
  > * `supersession.self-referential` and `supersession.illegal-kind-pair` → **ERROR**, name **flat**.
  >   These are RELATION-VALIDITY failures: `materialize` *raises* on both, so the corpus builds no
  >   graph at all. That verdict comes from the relation model, which already says which pairs are
  >   legal — it owes **nothing** to any per-kind status certification, so these do **not** wait on
  >   Task 12's ratchet and are **not** kind-scoped. Same defect whatever kind authors them.
  > * `<kind>.unbacked-inverse` → **WARN**, name **kind-scoped**. That one *is* about a status
  >   vocabulary (is this kind's `superseded` terminal certified?), and `gated_findings` filters on
  >   `Result.rule` alone. Task 12 owes it the flip to `severity_for_kind(kind)`.
  >
  > ### ⚠️ RULING 8b — THE CORPUS CLAIM IN THIS BOX WAS WRONG, and it was wrong in the direction that flatters the change
  >
  > *It read: "across all 18 roots the corpus authors **zero** `sci:supersedes` relations — the only
  > six grep hits are inside `<!-- Conclusion chains: -->` template boilerplate — so both ERROR rules
  > have a blast radius of exactly zero." **The grep was wrong.** The authored spelling is a
  > `relations:` block (`- predicate: "sci:supersedes"`), and counting it properly finds **16
  > `sci:supersedes` and 54 `sci:amends` edges live on disk** across `natural-systems`,
  > `cancer/therapeutics`, `r/cbioportal`, and `r/mm30`. I had certified an ERROR against an empty
  > set that was not empty — the exact move that put 472 findings into 5 projects last time. A
  > population check that returns zero deserves a second look, not a green light.*
  >
  > **The blast radius really is zero — but for a STRUCTURAL reason, which is the only kind worth
  > trusting.** `materialize` raises on all three defects, so a project that builds a graph today
  > *cannot* be carrying one. The rules can only fire on a corpus that already has no graph. Verified
  > by running `runner.run` over all seven projects that carry lineage edges or a `relations.yaml`:
  > **0 new ERRORs**, and the 4 pre-existing `unbacked-inverse` WARNs unchanged.
  >
  > *(The WARN is not free, and correctly so: **4** records author `superseded_by` — `3d-attention-bias/0004`,
  > `natural-systems/0043,0045,0047` — and every one is unbacked. Their real lineage is written in the
  > **withdrawn top-level `supersedes:` spelling** the Entity model silently drops. That is Task 9's
  > migration input, and the check earning its keep on day one.)*

  > ### ⚠️ RULING 9 — the check read a SUBSET of what it validates, and called a cycle a branch
  >
  > *Two more defects in the shipped builder, both found by review, both the same root cause as every
  > one before them: **this authority asked a narrower question than `materialize` asks.***
  >
  > **(a) ONE EDGE STREAM, NOT ONE CARRIER.** The builder scanned entity markdown for nested
  > `relations:`. `materialize` consumes `sources.relations`, which *also* unions
  > `knowledge/sources/<local>/relations.yaml` and the legacy models/parameters blocks. So a self-edge
  > or an illegal pair authored in `relations.yaml` refused to materialize while `validate` **and**
  > `mark_superseded --apply` both reported clean. Fixed by reading `sources.relations` — the same
  > objects, with the same `source_path`. **An authority that reads a subset of what it validates does
  > not validate.** Seven `relations.yaml` files exist on disk; none carries a lineage edge *today*,
  > so the hole was open and unexploited.
  >
  > **(b) A CYCLE IS NOT A BRANCH.** `_classify` collapsed both into one `non_linear` outcome — and
  > that outcome carries a *branch's* disposition: report, skip, **do not block**. But a branch
  > materializes (it is merely ambiguous about which node survives) while a cycle is a corpus
  > `materialize` **refuses to build** (`_validate_no_amendment_cycles`). So `--apply` returned clean
  > over a cyclic corpus, and `validate` said nothing at all. Now: `supersession.cycle`, **ERROR,
  > flat**, one finding per authored edge (breaking any edge on the cycle breaks it, so every edge is
  > a place to fix it), and `non_linear` narrows to **branched** only.
  >
  > **The cycle scan runs over the `{sci:amends, sci:supersedes}` FAMILY, because that is the scan
  > `materialize` runs** — it walks both predicates as one relation. `a supersedes b` + `b amends a`
  > is two *legal* edges, no self-reference, every per-edge rule green — and no graph. A
  > supersedes-only scan reports a clean linear chain and **offers to stamp `b`**. It also runs over
  > every *resolved* edge, not the *admitted* ones: `graph.edges` drops archived and commons targets,
  > which we cannot stamp but which `materialize` emits as real triples and traverses like any other
  > node. A cycle through a node we do not own is a cycle.
  >
  > **Known gap, stated rather than papered over:** a self-edge or an illegal endpoint on a bare
  > `sci:amends` relation also refuses to materialize, and nothing reports it. `amends` reaches this
  > module only through the acyclicity question. Its per-edge validity belongs to a check that does not
  > exist yet — and the general form of that check (*"every authored relation materializes"*) would
  > subsume all three ERROR rules here. **That is the real fix, and it is bigger than Task 7a.**
  >
  > *→ **RULING 10 built it, and everything above about "the check" is now history.** The three ERROR
  > rules named in this ruling no longer exist; they are `relation.self-referential`,
  > `relation.illegal-kind-pair` and `relation.cycle`, emitted by an audit that asks the graph builder
  > instead of imitating it. The `sci:amends` gap closed itself.*

  > ### ⚠️ RULING 10 — the SIXTH defect, and the one that ended the pattern: DELETE the second opinion
  >
  > **The defect.** `materialize`'s endpoint resolution is **asymmetric**: the OBJECT may resolve to a
  > live entity, an active **archived** row, or an external term, but the SUBJECT must be in
  > `entity_index` — it raises `Unknown canonical entity` otherwise. The builder's `IdResolution`
  > docstring asserted the opposite *as doctrine* ("it reads the resolved entity's kind, live or not,
  > and never asks who can write the file"), which is true of the object and **false of the subject**.
  > So an **archived** record could author a supersession into a **live** one, and
  > `mark_superseded --apply` **stamped it**:
  >
  > ```text
  > LIVE FM: status: superseded, superseded_by: interpretation:gone   # ← written to disk
  > MATERIALIZE: ValueError: Unknown canonical entity: interpretation:gone
  > ```
  >
  > A write that succeeds and leaves a corpus whose graph never builds. Only expressible through
  > `relations.yaml` (an archived entity's markdown is not a relation carrier) — which is why it
  > surfaced *only after* Ruling 9 taught the builder to read that carrier. **Each fix was exposing the
  > next facet of the same frame.**
  >
  > **The ruling: a second opinion is a second bug.** Six defects, six rounds, one cause — the
  > hand-written authority asked a NARROWER question than `materialize` asks. The fix is not a seventh
  > patch. `_add_authored_relation` was split into **`admit_authored_relation`** (resolve + validate,
  > pure, raises a typed `RelationRejection` carrying a rule `code`) and emission.
  > **`graph/relation_audit.py`** runs that admission over the whole `sources.relations` stream and
  > collects the refusals instead of raising on the first. `validate/checks/relations.py` reports them
  > as `relation.<code>`, ERROR, flat. **The 167-line admission ladder in `consolidation.py` is
  > deleted**, along with its four outcome buckets (`self_referential`, `mismatched`, `cycles`,
  > `unresolved_targets` → one `invalid`, which is not this module's verdict).
  >
  > **What that bought, for free, without writing a rule:** a bare `sci:amends` self-edge (the gap
  > Ruling 9 called unclosable), an unsupported `graph_layer`, a misused membership role, an external
  > target where the predicate requires an entity — *none of which were on anyone's list*.
  >
  > **What is left in `consolidation.py` is the one question it is actually the authority on:** the
  > edge is real — **can we stamp the thing it points at?** Archived (frozen: report, don't block),
  > unmanaged (not our markdown: report, don't block), or ours (stamp it). Legality, resolvability and
  > acyclicity are the builder's, asked once, in the builder's words.
  >
  > **THE BLAST RADIUS IS NOT ZERO, AND I CHECKED THIS TIME.** `3d-attention-bias` carries **5 real
  > `illegal-kind-pair` defects**: it authors `sci:tests` from `inquiry` and `workflow` subjects, and
  > the relation model allows only `task` / `experiment` / `workflow-run` there. `materialize_graph`
  > **already raises on that project today** — it has been silently unable to build a graph, and
  > `validate` said nothing. The structural argument holds (a project that builds a graph cannot carry
  > one of these), and the audit's verdict is `materialize`'s verdict, edge for edge — but the honest
  > consequence is that `validate` now FAILS there. **That is the project's defect to fix, not the
  > check's to soften.** Every other project with relations is clean: `natural-systems` (1646 admitted),
  > `mm30` (38), `seq-feats` (25), `therapeutics` (4), `cbioportal` (1).

**A check module is inert until it is BOTH decorated and imported.** `@Check` is what appends to
`CANONICAL_CHECKS` (`checks/__init__.py:84-87`), and `_load_canonical_checks` — which iterates
`CANONICAL_CHECK_MODULES` (`checks/__init__.py:25-76`) — is the only thing that *imports* the module
and therefore the only thing that ever *runs* the decorator. An earlier draft of this step wrote a
bare `def run(...)` and never touched the tuple, so `science validate` would not have imported the
file, would not have registered the check, and **would not have moved the snapshot count** — the very
signal this step tells you to regenerate. The instrument would have sat dead until Task 12's flip test
failed against a rule that had never once been emitted. **Both legs, or the check does not exist:**

```python
# science/src/science_tool/validate/checks/__init__.py -- the SECOND leg. Without this line the
# module is never imported, so `@Check` never runs and `CANONICAL_CHECKS` never learns about it.
CANONICAL_CHECK_MODULES = (
    ...,
    "methods",
    "supersession",      # <- Task 7a
)
```
```python
# science/src/science_tool/validate/checks/__init__.py -- the SECOND leg. Without this line the
# module is never imported, so `@Check` never runs and `CANONICAL_CHECKS` never learns about it.
CANONICAL_CHECK_MODULES = (
    ...,
    "methods",
    "relations",         # <- Task 7a / RULING 10: every authored relation must MATERIALIZE
    "supersession",      # <- Task 7a
)
```

```python
# science/src/science_tool/validate/checks/relations.py -- RELATION VALIDITY. RULING 10.
#
# IT WRITES NO RULES. `audit_relations` calls `admit_authored_relation` -- the graph builder's own
# admission, over the same `sources.relations` stream -- and this file turns each refusal into a
# `Result` named for the `code` the builder's own rejection carried. A rule the builder gains, this
# check gains. There is no second list to forget one from.
#
# ERROR and FLAT, never kind-scoped: these are RELATION-VALIDITY failures -- the corpus builds no
# graph at all -- and that verdict comes from the relation model, which owes nothing to any kind's
# status certification. Nothing here waits on Task 12's ratchet.
from collections.abc import Iterator

from science_tool.graph.relation_audit import audit_relations
from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


@Check(section="authored relations", order=28)
def check_authored_relations(ctx: ValidateContext) -> Iterator[Result]:
    audit = audit_relations(ctx.project_root, load_project_sources(ctx.project_root))

    for defect in audit.defects:
        yield Result(
            Severity.ERROR,
            # The file that AUTHORED the edge, off `SourceRelation.source_path` -- NOT the subject's
            # markdown. An edge in `relations.yaml` is a line in THAT file, and its subject may have
            # no markdown in this project at all.
            ctx.project_root / defect.path,
            None,
            defect.message,                    # materialize's own words, verbatim
            f"relation.{defect.code}",         # unknown-subject | self-referential | cycle | ...
            None,
        )
```

```python
# science/src/science_tool/validate/checks/supersession.py -- the STATUS-VOCABULARY question, and
# the ONLY thing left in this check. WARN and KIND-SCOPED, the other axis entirely: `gated_findings`
# filters on `Result.rule` ALONE, never on severity (`gates.py:59-62`), so a single generic
# `supersession.unbacked-inverse` in the `hygiene` tier would gate the WARN findings of every
# UNCERTIFIED kind too -- promoting the whole vocabulary the moment one kind earns it, which is the
# precise mistake the status-vocabulary incident was. Kind-scoped names advance one kind at a time.
@Check(section="supersession lineage", order=29)
def check_supersession(ctx: ValidateContext) -> Iterator[Result]:
    graph = build_supersedes_graph(load_supersession_inputs(ctx.project_root))

    for u in graph.unbacked_inverses:
        kind = graph.kind_by_id[u["id"]]
        # `Result` reports a FILE, which is why the graph carries `path_by_id`. An inverse is a
        # field on a RECORD, not an edge in a carrier -- located by id, not by `source_path`.
        yield Result(
            Severity.WARN,   # <- TASK 12 REPLACES THIS with `severity_for_kind(kind)`.
            graph.path_by_id[u["id"]],
            None,
            f"superseded_by: {u['superseder']} has no canonical sci:supersedes edge behind "
            f"it; author the edge on {u['superseder']} or drop the field",
            f"{kind}.unbacked-inverse",
            None,
        )
```

  **`unbacked-inverse` is WARN here, and Task 12 owes the flip.** The reason it is WARN *in this task*
  is the one the status-vocabulary post-mortem gave — severity is earned, and Phase 2 changes no
  meaning. And the corpus is **not** clean: **4** live records author a groundless `superseded_by`
  (Ruling 8b), and they have no migration until Task 9. ERROR today would break `validate` in two
  projects for a defect they cannot yet fix. *(The three relation-validity rules above are ERROR
  precisely because their blast radius is structurally zero — a corpus carrying one of them has no
  graph, so no project that builds today can be carrying one.)*

  **But a hard-coded WARN with an ERROR promised in a comment is exactly how `hypothesis.dangling-
  lineage` was left stranded** — Task 7 wrote "ERROR is Task 12's ratchet, per kind", and Task 12
  never touched the emitter. So this task does not merely leave a comment: **Task 12's Files list, its
  ratchet function, and its flip test all name this emitter**, and its suite fails if the `WARN` above
  survives. See Task 12.

  **The WARN is proved to fire HERE, through `run_validate` — not through a direct call to
  `check_supersession`.** That proves **wiring**: the check is reachable from the real entry point
  and fires on real input, rather than only when a test hands it a hand-built context.

  ☠️ **It does NOT prove registration, and this step used to claim it did.** `@Check` registers as an
  *import side effect*, so any file in the pytest process that imports `checks.supersession` registers
  the check whatever `CANONICAL_CHECK_MODULES` says — and then the end-to-end test passes over the
  unlisted module. Task 7 established exactly this for `verdict_agreement`, by mutation, and the same
  mutation was re-run here: with `"supersession"` dropped from the tuple, this file **alone** fails,
  but placed after any file that imports the check module, the run is **3 passed**. Green by import
  order. The registration guard is structural and already covers every check module on disk:
  `test_check_registry_is_complete.py::test_EVERY_check_module_on_disk_is_REGISTERED`, which compares
  the *directory* to the tuple and reads no registry state. **Nothing new is owed here** — the guard
  derives its scope from the filesystem, so a new check module joins it by existing.

```python
# science/tests/validate/test_check_supersession.py -- reuses the `_write` / `_supersedes` helpers.
def test_a_registered_check_fires_through_the_runner(tmp_path: Path) -> None:
    # WIRING, through `runner.run` -- not the registration guard (see above). A direct
    # `check_supersession(ctx)` call would prove even less: it cannot tell a registered check from an
    # unregistered one. `interpretation` is the kind used because it can carry the field TODAY: no
    # migration, no pin, and it stays WARN through Task 12 (the uncertified-kind control there).
    _write(tmp_path, "interpretations", "i1", {"id": "interpretation:i1", "kind": "interpretation",
                                               "status": "superseded",
                                               "superseded_by": "interpretation:i2"})  # no edge behind it
    _write(tmp_path, "interpretations", "i2", {"id": "interpretation:i2",
                                               "kind": "interpretation"})   # resolves; grounds nothing

    findings = [r for r in run_validate(tmp_path) if r.rule == "interpretation.unbacked-inverse"]

    assert len(findings) == 1
    assert findings[0].severity is Severity.WARN
    assert findings[0].path == tmp_path / "entities/interpretations/i1.md"


def test_a_BACKED_inverse_is_silent(tmp_path: Path) -> None:
    # The control that makes the check falsifiable. Same corpus, one edge added -- and the finding has
    # to disappear, or the rule is just "any superseded_by is a finding" wearing a better name.
    _write(tmp_path, "interpretations", "i1", {"id": "interpretation:i1", "kind": "interpretation",
                                               "status": "superseded",
                                               "superseded_by": "interpretation:i2"})
    _write(tmp_path, "interpretations", "i2", {"id": "interpretation:i2", "kind": "interpretation",
                                               "relations": [_supersedes("interpretation:i1")]})

    assert [r for r in run_validate(tmp_path) if r.rule.endswith(".unbacked-inverse")] == []
```

  **Regenerate `science/tests/validate/snapshots/text_default.txt` in the same commit** — the check
  count moves. A new check landed without its snapshot once already (`5c2b44f1`), and the byte-identity
  gate sat red at main tip until someone noticed.

- [x] **Step 6: Full gates.** `cd science/model && uv run --frozen pytest` / `cd science && uv run
  --frozen pytest`, both whole; `uv run ruff check` and `uv run pyright`; and the snapshot marker,
  `env -u FORCE_COLOR uv run --frozen pytest -m snapshot` (excluded by default — Step 5d moves it).
  The `materialize` path is the one at risk: leg 2 changes a `RelationKind`, and the graph builders
  read it.
- [x] **Step 7: Commit** — **this task's three legs in ONE commit**: the schema admission (Step 3),
  the relation endpoint (Step 4), and the operation (Steps 5–5d). A bidirectional gate exists to catch
  half-wiring; landing half of *these* would be the defect it was written to detect.

  **The triangle is still open when this commit lands, and that is correct.** The fourth leg —
  `superseded` in the hypothesis descriptor, the *vocabulary* — is **Task 8's**, and it is
  deliberately last: it is the leg that admits `hypothesis` into the gate's derived `declares
  superseded` population, so landing it before the other three would take the half-wired count from
  twelve to thirteen and fail `test_every_supersedable_kind_can_author_the_CANONICAL_edge`. Phase 2
  stays meaning-neutral; **Task 8 closes the triangle**, and it is where the hypothesis apply-tests
  live, because that is the first moment they can pass.

---

## Phase 3 — The `hypothesis` P2m slice (this is where meaning changes)

> **ATOMIC PER KIND, ACROSS THE CERTIFIED ROSTER: 18 project roots in 15 git repositories.** That
> roster is the one **derived** by `field_inventory` (Task 11 Step 0) — never a hand list, and never
> the "9 repos" this plan said through Rev 3. `default_profile_for_kind` is **global** — the instant
> Task 9 wires schema validation into the load path, *every* project's hypotheses are validated
> against the new mixin. Rev 1 migrated one repo and expected the rest to keep validating.
> **They cannot.** Two options existed; this is the one taken:
>
> ☠️ **THE STALE SCOPE IN THIS HEADER IS THE DEFECT THAT STRANDED 62 HYPOTHESES.** "9 repos" was not
> a typo — it was a count nobody re-derived, and the per-repo numbers under it summed to **85 of 147**
> (§ "147 authored hypotheses — across 18 project roots, not 9 repos"). Migrating on that scope leaves
> **62 hypotheses on the old meaning, `validate` green, in projects nobody is watching.** A root is
> not a repo, and neither number may be typed from memory here: both come from Task 11 Step 0.
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

> **Task 7a's gate is load-bearing HERE.** `hypothesis` does not declare `superseded` today — its
> `EntityKind.statuses` are `[proposed, under-investigation, partially-supported, supported,
> weakened, refuted, archived]`, the **verdict** vocabulary. **This task is where it joins the
> "declares `superseded`" population.** Land it without Task 7a and
> `test_every_supersedable_kind_can_author_the_CANONICAL_edge` goes from twelve half-wired kinds to
> **thirteen** and fails — which is exactly what a bidirectional gate is for. It is the one
> instrument that would have caught this plan shipping a terminal status for a kind that could not
> reach it.
>
> **And this task is where hypothesis supersession becomes EXECUTABLE**, so it inherits the three
> tests Task 7a could not run: `_supports_superseded("hypothesis")` is `False` until the descriptor
> below declares `superseded`, so `mark_superseded` routes every hypothesis to `skipped_kinds` and
> writes nothing. **Step 3c-ii below is the closure of the D4 triangle** — Task 7a builds the
> machinery on `interpretation`; this task is the first moment it can be pointed at a hypothesis.

- [x] **Step 3c-ii: The hypothesis supersession tests — executable for the first time.**

```python
# science/tests/test_consolidation_mark_superseded.py
def test_a_stamped_HYPOTHESIS_satisfies_its_own_schema(tmp_path: Path) -> None:
    # THE TRIANGLE, CLOSED -- and the first hypothesis ever superseded by this toolkit. All three
    # legs must agree at once: the schema admits the edge (7a leg 1), the relation admits the
    # endpoint pair (7a leg 2), the operation writes a resolvable inverse (7a leg 3), and the
    # descriptor (THIS task) makes `superseded` a status the kind can hold. Any one missing and
    # this fails -- which is the whole reason a bidirectional gate is written as one assertion.
    _write_hypothesis(tmp_path, "0001-old", status="active")
    _write_hypothesis(tmp_path, "0002-new", status="active",
                      relations=[{"predicate": "sci:supersedes", "target": "hypothesis:0001-old"}])

    report = mark_superseded(tmp_path, apply=True)
    fm = read_frontmatter(tmp_path / "entities/hypotheses/0001-old.md")

    assert report["applied"] == ["hypothesis:0001-old"]     # NOT skipped_kinds -- the 7a failure mode
    assert fm["status"] == "superseded"
    assert fm["superseded_by"] == "hypothesis:0002-new"
    _V.validate_as(fm, _PROFILE)                                           # schema agrees
    # ...and it RESOLVES. Through the SAME resolver semantics the loader and materialize use --
    # not a raw id set, which would both reject a valid alias and miss a self-alias (Task 7).
    targets = ReferenceResolver.from_entities(_load_entities(tmp_path))
    assert check_resolution(
        fm, targets=targets, live_hypotheses={"hypothesis:0002-new"}
    ) == []


def test_a_hypothesis_CHAIN_records_the_immediate_superseder(tmp_path: Path) -> None:
    # A -> B -> C, on the kind that matters. Task 7a proves the inversion on `interpretation`;
    # this proves the descriptor change did not quietly re-route hypotheses down the skip path.
    for n in ("0001-a", "0002-b", "0003-c"):
        _write_hypothesis(tmp_path, n, status="active")
    _relate(tmp_path, "0002-b", supersedes="hypothesis:0003-c")
    _relate(tmp_path, "0001-a", supersedes="hypothesis:0002-b")

    mark_superseded(tmp_path, apply=True)

    c = read_frontmatter(tmp_path / "entities/hypotheses/0003-c.md")
    assert c["superseded_by"] == "hypothesis:0002-b"        # NOT 0001-a, the survivor


def test_an_INTERPRETATION_may_not_supersede_a_HYPOTHESIS(tmp_path: Path) -> None:
    # The cross-kind case Task 7a could only test in the abstract. `interpretation -> hypothesis` is
    # not an allowed pair, and if the operation wrote it anyway the record would carry
    # `superseded_by: interpretation:...` -- which the mixin's `^hypothesis:` pattern rejects.
    #
    # ☠️ THE CONTRACT CHANGED UNDER THIS TEST, and an earlier draft asserted the OLD one: it read
    # `report["mismatched_kinds"]` (a key that no longer exists) and expected `apply=True` to return
    # a clean report. Both are now wrong, and wrong in the safe direction. The refusal is the
    # relation audit's -- `materialize`'s own admission, asked once -- so the edge is REFUSED rather
    # than filed in a writer-side bucket, and a corpus carrying ANY unbuildable relation gets no
    # derived lineage at all. `apply=True` RAISES.
    _write_hypothesis(tmp_path, "0001-x", status="active")
    _write(tmp_path, "interpretations", "i-v1",
           {"id": "interpretation:i-v1", "kind": "interpretation",
            "relations": [_supersedes("hypothesis:0001-x")]})
    before = (tmp_path / "entities/hypotheses/0001-x.md").read_bytes()

    report = mark_superseded(tmp_path, apply=False)      # REPORT names the rule that fired...

    assert report["applied"] == []
    assert [d["code"] for d in report["invalid_relations"]] == ["illegal-kind-pair"]
    assert report["invalid_relations"][0]["subject"] == "interpretation:i-v1"
    assert report["invalid_relations"][0]["object"] == "hypothesis:0001-x"

    with pytest.raises(SupersessionError):               # ...and APPLY refuses the whole corpus.
        mark_superseded(tmp_path, apply=True)

    # BYTE-UNCHANGED, not merely "superseded_by absent". A blocked apply must leave the corpus
    # exactly as it found it -- the all-or-none contract is about the FILE, not about one key.
    assert (tmp_path / "entities/hypotheses/0001-x.md").read_bytes() == before
```

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py:32-51`
- Modify: `science/model/src/science_model/entities.py:797-839` (`HypothesisEntity`) **and `Entity`
  (`description`, Step 3b-ii — a base-declared field that no model could hold)**
  *(`RivalModelPacket` is **not** modified here — its four fields landed in Task 6, Step 3c, with
  the closed `$def` that requires them.)*
- Modify: `science/src/science_tool/entities.py` (`_LIVE_STATUSES`)
- Modify: `science/model/src/science_model/templates/hypothesis.md` **and** `templates/hypothesis.md` — **two copies; the packaged one is what the Renderer reads**
- Modify: the `science.yaml` schema to admit `entity_schema_version: int`
- Test: `science/model/tests/test_hypothesis_entity.py`
- **Test: `science/tests/test_hypothesis_schema_reconciliation.py`** — one test, and it cannot live
  in the model suite: `capability_scope`'s vocabulary (`VALID_SCOPES`) is owned by **`science_tool`**,
  and `science_model` must not import its own consumer. The mixin duplicates that vocabulary, so
  something has to reconcile it, and this is the only package that can see both:

```python
# science/tests/test_hypothesis_schema_reconciliation.py
import json
from importlib.resources import files

from science_tool.datasets.capability_scope import VALID_SCOPES


def test_the_capability_scope_vocabulary_is_not_a_SECOND_authority() -> None:
    # The mixin hard-codes this enum because JSON Schema cannot import Python. Add a scope to
    # `CAPABILITY_SCOPE_VALUES` without regenerating the mixin and every hypothesis that authors
    # the new scope fails validation -- with an error naming the enum, not the vocabulary.
    mixin = json.loads(
        (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
    )

    assert sorted(mixin["properties"]["capability_scope"]["enum"]) == sorted(VALID_SCOPES)
```

- [x] **Step 1: Write the failing test**

```python
# science/model/tests/test_hypothesis_entity.py
import json
from importlib.resources import files
from typing import Any

import pytest
from pydantic import ValidationError

from science_model.entities import HypothesisEntity
from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    default_profile_for_kind,
)
from science_model.profiles.core import CORE_PROFILE

MIXIN = json.loads(
    (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
)
BASE_2 = json.loads(
    (files("science_model.schemas") / "science-entity-base-2.0.json").read_text(encoding="utf-8")
)["properties"]
_PROFILE = default_profile_for_kind("hypothesis")
_V = EntityValidator()

# Admitted by the COMPOSED profile = what the base declares (minus what the mixin forbids) plus what
# the mixin declares. Deriving this from the mixin ALONE is how `description` hid for four drafts:
# it is CORE (Task 2 §4), authored by 3 files, declared in base 2.0 -- and on no model.
_ADMITTED = (
    {n for n in BASE_2 if MIXIN["properties"].get(n) is not False}
    | {n for n, s in MIXIN["properties"].items() if s is not False}
)

# Admitted by the schema, absent from the model, and CORRECT -- for exactly one reason: these two
# are the P1 capability subsystem, whose readers re-parse RAW frontmatter
# (`dataset_prioritize.py:511,525`; `validate/checks/dataset_capabilities.py:113,141`) and never go
# through the model at all. The value is not dropped; it is read by another path. Absorbing them is
# P1, and P1 DELETES this exception -- it must never grow a third member without a reader named
# beside it.
_NOT_ON_THE_MODEL = {"required_capabilities", "capability_scope"}

# The fields BOTH authorities describe. Derived from `_ADMITTED`, so the base surface
# (`created`, `updated`, `title`, `description`, `ontology_terms`, `same_as`, `dataset_usage`) is
# reconciled too. `false` properties are excluded by `_ADMITTED`: the schema rejects them outright,
# so "at least as strict" holds trivially and there is nothing to compare.
_SHARED_FIELDS = _ADMITTED & set(HypothesisEntity.model_fields)

# Model-only required fields. NOT frontmatter -- the loader stamps them -- so they never appear in
# a schema payload, and every direct model construction in this file goes through `_model_payload`
# rather than hand-listing them (and forgetting three).
_MODEL_ONLY: dict[str, Any] = {"project": "p", "file_path": "h.md", "content_preview": "",
                               "ontology_terms": [], "related": [], "source_refs": []}


def _payload(**over: Any) -> dict[str, Any]:
    return {"id": "hypothesis:0001-x", "kind": "hypothesis", "title": "T",
            "created": "2026-07-13", "updated": "2026-07-13", "status": "active", **over}


def _model_payload(**over: Any) -> dict[str, Any]:
    return _MODEL_ONLY | _payload(**over)


def _schema_accepts(field: str, value: Any) -> bool:
    try:
        _V.validate_as(_payload(**{field: value}), _PROFILE)
        return True
    except EntityValidationError:
        return False


def _model_accepts(field: str, value: Any) -> bool:
    try:
        HypothesisEntity.model_validate(_model_payload(**{field: value}))
        return True
    except ValidationError:
        return False


def _survives(authored: Any, dumped: Any) -> bool:
    """Every authored path is still present, with its value, after the round trip.

    NOT `dumped == authored`: a dump legitimately carries defaults the author never wrote. The
    claim is one-directional -- nothing the author WROTE may vanish.
    """
    if isinstance(authored, dict):
        return all(k in dumped and _survives(v, dumped[k]) for k, v in authored.items())
    if isinstance(authored, list):
        return len(authored) == len(dumped) and all(map(_survives, authored, dumped))
    return authored == dumped


def _model_preserves(field: str, value: Any) -> bool:
    dumped = HypothesisEntity.model_validate(_model_payload(**{field: value})).model_dump(
        mode="json"  # dates -> ISO strings, enums -> values, so it compares to AUTHORED yaml
    )
    return field in dumped and _survives(value, dumped[field])


def _kind():
    return next(k for k in CORE_PROFILE.entity_kinds if k.name == "hypothesis")


def test_descriptor_declares_the_lifecycle_not_the_verdict() -> None:
    assert sorted(_kind().statuses) == sorted(
        ["draft", "active", "complete", "superseded", "retired", "archived"]
    )
    assert _kind().default_status == "active"


def test_verdict_and_closure_basis_are_first_class_fields() -> None:
    h = HypothesisEntity.model_validate(_model_payload(verdict="refuted"))
    assert h.verdict == "refuted"


def test_disposition_is_gone() -> None:
    assert "disposition" not in HypothesisEntity.model_fields
    assert "disposition_basis" not in HypothesisEntity.model_fields


def test_the_projection_does_NOT_reimplement_the_schema_invariants() -> None:
    # D3: JSON Schema is THE authority; Pydantic is a PROJECTION. Rev 1 duplicated
    # `complete requires a verdict` as a model_validator -- which recreates the second authority D3
    # exists to abolish, and guarantees the two eventually disagree. The projection must be able to
    # REPRESENT anything the schema admits, and must not independently police it.
    HypothesisEntity.model_validate(_model_payload(status="complete"))  # SCHEMA rejects; model must not
    assert not _schema_accepts("status", "complete")  # ...and the schema DOES. Both halves, or neither.


def test_every_field_the_schema_ADMITS_is_REPRESENTABLE_in_the_projection() -> None:
    # D3 point 4, half one. A field the schema admits but the projection cannot hold is a field
    # that validates on disk and is SILENTLY DROPPED on load (`Entity` is `extra="ignore"`) --
    # which is `phase`'s entire history, and the reason this arc exists. `description` was the
    # third instance, and it survived every earlier draft of this plan because no test looked at
    # the fields the BASE contributes.
    missing = _ADMITTED - set(HypothesisEntity.model_fields) - _NOT_ON_THE_MODEL
    assert not missing, f"schema admits {sorted(missing)}; the projection would silently drop them"


@pytest.mark.parametrize("field", sorted(_SHARED_FIELDS))
def test_the_schema_is_at_least_as_strict_as_the_projection(field: str) -> None:
    """D3 point 4, half two — and the one that actually bites.

    The design says *"JSON Schema is authoritative for shape and invariants; Pydantic is a
    projection."* That sentence has an executable meaning, and this is it: **no payload the schema
    accepts may be rejected by the model.** If one is, the model is the real authority for that
    field and the schema is decoration.

    The first draft of `mixin-hypothesis` failed this on FIVE fields at once (`origins`,
    `review_state`, `composition_rule`, `rival_model_packet`, `datasets`) because each was declared
    `{}` or as a bare array -- and the old reconciliation test, which compared three field NAMES
    and the status enum, could not see any of it. Names are not contracts.

    The converse is NOT asserted: the schema may be STRICTER (it forbids unknown nested keys the
    model would ignore, and it enforces `complete -> verdict`, which the model deliberately does
    not). Strictness beyond the projection is the design working as intended.
    """
    for value in _BATTERY[field]:
        schema_ok = _schema_accepts(field, value)
        model_ok = _model_accepts(field, value)
        assert not (schema_ok and not model_ok), (
            f"{field}={value!r}: the SCHEMA admits it and the MODEL rejects it. "
            f"The schema is not authoritative for this field."
        )

    # Anti-tautology: a battery the schema accepts in full is a battery that proves nothing. If
    # this fires, the field's contract is vacuous (or the battery is) -- exactly the state the
    # five `{}` declarations were in, where every test still passed.
    assert any(not _schema_accepts(field, v) for v in _BATTERY[field]), (
        f"{field}: the schema rejected NOTHING in the battery -- its contract admits anything"
    )


@pytest.mark.parametrize("field", sorted(_SHARED_FIELDS))
def test_every_value_the_schema_ADMITS_SURVIVES_the_projection(field: str) -> None:
    """D3 point 4, half three — the half that "the model accepted it" cannot see.

    Acceptance and preservation are DIFFERENT properties, and `extra="ignore"` is exactly the gap
    between them: the model accepts the object, and `model_dump()` loses the keys it did not
    declare. `rival_model_packet` sat in that gap -- schema admits the four single-rival keys,
    Pydantic accepts the object, four authored values gone. Every test in the earlier draft passed.

    A field that validates on disk and evaporates on load is not a contract; it is a **trap**, and
    it is precisely `phase`'s failure mode reappearing one nesting level down. So the claim is not
    "the model tolerated it" but "the author's value is still there afterwards."
    """
    for value in _BATTERY[field]:
        if not _schema_accepts(field, value):
            continue  # the schema already refused it; nothing is owed
        assert _model_preserves(field, value), (
            f"{field}={value!r}: the SCHEMA admits it, the MODEL accepts it, and `model_dump()` "
            f"DROPS it. The value validates and then evaporates."
        )


def test_the_lens_vocabulary_is_not_a_SECOND_authority() -> None:
    # The mixin hard-codes the lens enum because JSON Schema cannot call Python. That duplication
    # is only safe while THIS test exists: add a lens to `LENS_SLUGS` without regenerating the
    # mixin and every hypothesis authoring it fails validation with no hint why.
    from science_model.lenses import LENS_SLUGS

    assert sorted(MIXIN["$defs"]["lens_view"]["properties"]["lens"]["enum"]) == sorted(LENS_SLUGS)


def test_the_status_vocabulary_is_not_a_SECOND_authority() -> None:
    descriptor = next(k for k in CORE_PROFILE.entity_kinds if k.name == "hypothesis")
    assert sorted(MIXIN["properties"]["status"]["enum"]) == sorted(descriptor.statuses)


def test_the_composition_rule_vocabulary_is_not_a_SECOND_authority() -> None:
    # The IMPLEMENTED rules, not every name `CompositionRule` declares. `evidence_union` and
    # `faceted_support` are RESERVED and rejected by `Entity._validate_composition_rule` -- so a
    # schema enumerating all four would admit two values the model refuses, which is the exact
    # schema-is-not-authoritative defect this test exists to prevent, committed BY this test.
    from science_model.reasoning import WEAKEST_LINK_COMPOSITION_RULES

    assert sorted(MIXIN["properties"]["composition_rule"]["enum"]) == sorted(
        r.value for r in WEAKEST_LINK_COMPOSITION_RULES
    )


def test_the_BATTERY_is_EXACTLY_the_shared_surface() -> None:
    # EQUALITY, not coverage. `_SHARED_FIELDS` is derived; the battery is hand-written -- so the
    # battery is the half that falls behind, and it falls behind in BOTH directions:
    #
    #   missing  -> a field is declared by both authorities and reconciled by neither, while every
    #              test still passes. (`description` and the whole base surface lived here.)
    #   spurious -> a battery entry for a field nobody declares. It never runs, and it reads like
    #              coverage that does not exist -- which is worse than no entry at all.
    assert set(_BATTERY) == _SHARED_FIELDS, (
        f"unreconciled: {sorted(_SHARED_FIELDS - set(_BATTERY))}; "
        f"stale: {sorted(set(_BATTERY) - _SHARED_FIELDS)}"
    )
```

**The battery** (same file, above the tests). Every value is one the *model* has an opinion about;
the point is to make the schema hold the same opinions. **It must equal `_SHARED_FIELDS` exactly** —
`test_the_BATTERY_is_EXACTLY_the_shared_surface` enforces that, in both directions.

```python
_LEGAL_ORIGIN = {"type": "literature", "ref": "paper:Smith2024"}
_LEGAL_LENS = {"lens": "mechanism", "rationale": "r"}

_BATTERY: dict[str, list[Any]] = {
    # The five that shipped VACUOUS. Each leading value is one the old mixin admitted.
    "origins": [[42], 42, [{}], [{"type": "nope"}], [{"type": "literature"}],
                [{"type": "literature", "ref": "topic:x"}],   # ref must be paper:/cite:
                [dict(_LEGAL_ORIGIN, bogus=1)],               # extra="forbid"
                [dict(_LEGAL_ORIGIN, date="2026-02-31")],     # must be a real calendar date
                [_LEGAL_ORIGIN]],                             # the control: passes BOTH
    "review_state": [42, "x", {"review_horizon_days": 0}, {"review_horizon_days": "x"},
                     {"last_reviewed": "nope"}, {"bogus": 1},
                     {"last_reviewed": "2026-07-13", "review_horizon_days": 90}],
    # The RESERVED rules are the point: `Entity._validate_composition_rule` rejects both, so a
    # schema that enumerated all four of `CompositionRule` would admit values the model refuses.
    "composition_rule": [42, "nope", "evidence_union", "faceted_support", "conjunctive"],
    # The single-rival form (ruled in Task 6) must SURVIVE, not merely validate -- this entry is
    # what `test_every_value_the_schema_ADMITS_SURVIVES_the_projection` runs on.
    "rival_model_packet": [42, {}, {"packet_id": ""}, {"packet_id": "p", "alternative_models": [42]},
                           {"packet_id": "p", "bogus": 1},
                           {"packet_id": "p", "rival_id": "platonic", "rival_name": "PRH",
                            "rival_claim": "representations converge",
                            "discriminator_status": "pre-registered"},
                           {"packet_id": "p"}],
    "datasets": [[42], 42, ["dataset:x"]],
    "lens_views": [[42], [{"lens": "nope", "rationale": "r"}], [{"lens": "mechanism"}],
                   [{"lens": "mechanism", "rationale": " "}], [dict(_LEGAL_LENS, bogus=1)],
                   [_LEGAL_LENS]],
    # The BASE surface. Omitting it is how `description` stayed unreconciled: it is declared by
    # base 2.0, never by the mixin, so a battery derived from mixin properties could not see it.
    "title": [42, "T"],
    "description": [42, "a description"],
    "created": [42, "x", "2026-13-01", "2026-07-13"],
    "updated": [42, "x", "2026-07-13"],
    "ontology_terms": [42, [42], ["GO:0008150"]],
    "same_as": [42, [42], ["hypothesis:0002-y"]],
    "dataset_usage": [42, [{"ref": "x", "role": "analyzed"}],          # ref must be `^dataset:`
                      [{"ref": "dataset:x", "role": "nope"}],          # role is an enum
                      [{"ref": "dataset:x"}],                          # role is required
                      [{"ref": "dataset:x", "role": "analyzed"}]],
    # The rest of the mixin surface.
    "related": [42, [42], ["hypothesis:0002-y"]],
    "source_refs": [42, [42], ["papers/x.md"]],
    "aliases": [42, [42], ["alias"]],
    "added_by": [42, "science:explore-ideas"],
    "profile": [42, "core"],
    "id": [42, "topic:x", "hypothesis:0001-x"],
    "kind": [42, "dataset", "hypothesis"],
    "status": [42, "nope", "active"],
    "verdict": [42, "nope", "refuted"],
    "closure_basis": [42, "", "the assay was discontinued"],
    "superseded_by": [42, "topic:x", "hypothesis:0002-y"],
    "resynthesized_into": [42, [42], ["topic:x"], [], ["hypothesis:0002-y"]],
    # ADDED BY TASK 7a, and the battery MUST grow with it. `_SHARED_FIELDS` is derived
    # (`_ADMITTED & HypothesisEntity.model_fields`), `relations` is admitted by the mixin (7a leg 1)
    # and inherited from `Entity` (entities.py:315) -- so the derived set gains it, the hand-written
    # battery does not, and `test_the_BATTERY_is_EXACTLY_the_shared_surface` fails. That failure is
    # the feature: the battery is the half that falls behind, and this is it being caught doing so.
    "relations": [42, [42], [{}],
                  [{"predicate": "sci:supersedes"}],                  # `target` is required
                  [{"target": "hypothesis:0002-y"}],                  # `predicate` is required
                  [{"predicate": " ", "target": "hypothesis:0002-y"}],  # non-empty
                  [{"predicate": "sci:supersedes", "target": "hypothesis:0002-y",
                    "tarrget": "typo"}],                              # additionalProperties: false
                  [{"predicate": "sci:supersedes", "target": "hypothesis:0002-y"}],       # control
                  [{"predicate": "sci:supersedes", "target": "hypothesis:0002-y",
                    "graph_layer": "graph/knowledge"}]],              # control, explicit layer
}
```

> **Which `model_validator`s may survive Step 3b's "no re-implementation" rule.** The rule bans a
> validator that **re-implements an invariant the schema expresses** (`complete → verdict`) — that
> builds the second authority D3 abolishes. It does **not** ban validators for invariants JSON
> Schema *cannot* express, and two of those exist on `Entity` today and must stay:
> `_validate_lens_views` (a `lens_view.origin_ref` must match one of **this entity's own**
> `origins[].ref` — a cross-*property* value comparison, which JSON Schema has no operator for) and
> `_validate_review_state_kind` (gated on `kind`, which the mixin has already pinned by `const`).
> The battery above deliberately keeps `origin_ref` out of its `lens_views` payloads so it tests
> *shape*, not those invariants. **Delete either validator and nothing replaces it.**

- [x] **Step 2: Run and fail.**

- [x] **Step 3: Rewrite the descriptor** (`profiles/core.py`):

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
```

> **These four fields land in TASK 7, not here** — Task 7's lineage check reads them, and a check
> cannot observe a field the model drops. They are shown here because Task 8's reconciliation
> battery is what *certifies* them against the schema; by the time this task runs they already
> exist. **`archive_ref` is gone entirely** (Task 6 — no reader, no author, no resolvable
> namespace).

**Step 3b-ii — `description` on `Entity`** (`entities.py`, beside `title`). **One line, and it closes
a live silent drop** found by `test_every_field_the_schema_ADMITS_is_REPRESENTABLE_in_the_projection`:

```python
    description: str = ""
```

> **`description` is the third `phase`.** Base 1.0 *and* 2.0 declare it, Task 2 §4 ruled it **CORE**,
> **3 hypothesis files author it** — and `Entity` has no such field, so `extra="ignore"` has been
> **discarding it at `model_validate` all along.** It validates, it looks declared, and it reaches
> nothing. It goes on `Entity` (not `HypothesisEntity`) because the *base* is what declares it, so
> every kind has been dropping it equally — including the commons kinds, whose records are the ones
> that most obviously *have* descriptions.
>
> Precisely: the *body prose* is read pre-validation into `content_preview`, so a hypothesis is not
> wholly unread — but the **`description` field itself** is dropped, and `materialize.py:639` emits
> `summary`, **not** `description`. So the authored key reaches no model attribute and no triple.
>
> The field is now **representable**; it is **not yet materialized** to the graph (no triple, no
> consumer). That is a deliberate stopping point, not an oversight: this arc migrates a lifecycle,
> and quietly adding a new predicate to `graph.trig` would put an unrelated change inside the
> migration's diff — exactly what Task 11's before/after graph diff exists to detect. **Ending the
> drop is this plan's business; deciding what a description *means* to the graph is not.**

> **The single-rival `RivalModelPacket` fields are NOT here — they landed in Task 6, Step 3c**, with
> the closed `$def` that requires them. Splitting the pair across tasks would leave
> `protein-landscape/0001` failing validation for the whole interval: Task 6 already ships
> `validate_as` and the hypothesis profile, so the mismatch would be **observable**, not theoretical.
> *Schema and model move together* names a window that must be zero, and a plan that opens it has
> already lost the argument.
>
> What remains true here: `test_every_value_the_schema_ADMITS_SURVIVES_the_projection` is what proves
> the packet survives, and it is worth being explicit about why the obvious test would **not** have.
> Pydantic *accepted* that packet all along — `extra="ignore"` accepts and discards. **Acceptance was
> never the property worth asserting**; survival is.

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

- [x] **Step 4: Green — both suites, plus ruff and pyright.** Consumers that read the old
  vocabulary are updated in **Task 10**, so run Task 10's edits together with this task's if the
  suite is red at this point. **Do not commit red** (rev 1 explicitly told the implementer to,
  which is both a broken task and a contradiction of its own atomicity claim).

- [x] **Step 5: Commit.**

---

### Task 9: The migration — two-phase, all-or-none, per repo

> ### ☠️ REV 7 — THIS TASK IS THREE THINGS, AND THEY ARE ONE UNIT. Read before writing any code.
>
> Revs 1–6 scoped Task 9 as "rewrite the status field". That is **not a migration this corpus can
> survive**, for a reason the review surfaced and the task's own inputs prove:
>
> 1. **The projection still drops what the schema admits.** `Entity` is `extra="ignore"`, so a
>    schema-valid **project-extension** field validates on disk and evaporates at `model_validate`.
>    Verified, on the three real ones: `confidence_mechanistic_label`, `identification`,
>    `source_stated_evidence` — all three absent from `model_dump()`. **This makes the migration's own
>    renames unsound.** Task 2 rules `author_stated_evidence` → **`source_stated_evidence`** on 13
>    evolution files, and that target is declared **only in a project extension**. Rewrite the 13 files
>    and the loader discards the field on the very next read: the string survives on disk and reaches
>    nothing. Task 2's own words, one level down — *a rename whose target nobody declared is a delete
>    with better manners.* Declared in the SCHEMA, undeclared in the PROJECTION, is that delete.
> 2. **D3.3 is the design's, not this task's invention**: *"Projections MUST preserve schema-valid
>    extension fields. Never return to `extra="ignore"` — that is the original defect."* No task owned
>    it. It is owned here, because here is where the schema starts being enforced.
> 3. **`extra="allow"` alone would preserve garbage**, so it lands **with** D3.1 — schema-first
>    validation — and not before. Together they are the contract: the SCHEMA refuses unknown keys, the
>    PROJECTION preserves the ones it admitted. Apart, each is a defect: validation without
>    preservation is a rename that deletes; preservation without validation is `extra="allow"` over an
>    unvalidated corpus.
>
> So Task 9 ships **the projection (D3.3), the load path (D3.1/D3.2), and the migration** in one
> commit. They cannot be separated: you cannot arm validation without the pin, and you cannot set the
> pin on files whose rename targets the loader throws away.
>
> **And the migration is the FULL field adjudication, not the status cross-tab.** Revs 1–6 dropped
> `phase`/`disposition`/`disposition_basis` and stopped. `docs/plans/2026-07-12-hypothesis-field-adjudication.md`
> is the authority, and it rules **eight deletes**, **two renames**, and **one refusal** besides:
>
> | disposition | keys | mechanism |
> |---|---|---|
> | **delete** | `phase` (107), `belief_state` (13), `evidence_stance` (13), `tags` (11), `priority` (8), `role` (2), `promotion_criteria` (2), `domain` (2) | strip the key; the mixin marks each `false`, so a leftover fails LOUDLY |
> | **rename** | `author_stated_evidence` → `source_stated_evidence` (13, evolution) | value preserved **byte-for-byte**; the target must be *representable*, which is why (1) above blocks |
> | **project-extension** | `identification`, `confidence_label`, `confidence_mechanistic_label` (mm30); `external_hypothesis_id` (evolution); **`promoted_from` (3, protein-landscape — moved out of RENAME 2026-07-14)** | the migration **leaves them alone**. They are admitted by the project's composed schema and preserved by the projection (D3.3). ☠️ **`promoted_from` → `origins` was NOT PERFORMABLE:** `OriginRecord.type` is a required enum (*who* had the idea) and the authored values are source paths (*where* it came from). Picking a type is fabricated provenance — the identical objection that already kept `author_stated_evidence` out of `origins`, raised for one field and not carried to the one beside it. |
> | **cross-tab** | `status` + `phase` → `status` (lifecycle) + `verdict` (epistemic) | `status_inventory`, entirely — this module adds no rule of its own |
> | **☠️ REFUSE** | `confidence` (2, 3d-attention-bias) | **`0.7` and `0.75` name no proposition, stance, source, strength, or independence group.** The migration STOPS and names the files. The author decomposes each scalar into proposition-targeted `expert_judgment` evidence lines, or deletes it. *A migration that guessed here would be manufacturing provenance* — the D5 refusal contract, applied to a field instead of a status. |
>
> `disposition`/`disposition_basis` need **no migration step**: the corpus authored them on **zero of
> 147** hypotheses, and Task 8 deleted the fields with their only reader.

> **⚠️ Four fixture files must be backfilled here, or the preflight fails on our own repo.** Base 2.0
> **requires** `created` and `updated`. The certified corpus is **147 = 143 non-fixture + 4 fixture**,
> and Task 2's inventory already reported **`created`/`updated` on exactly 143** — so the arithmetic
> was sitting in the artifact the whole time: **the 4 files missing them ARE the 4 fixture
> hypotheses**, not four more on top.
>
> `big_picture/minimal_project/{h1-alpha,h2-beta}.md`, `commons_mm30_canary/h4-attractor-convergence.md`,
> `spec_y_kitchen_sink/h01.md`. (The canary is also the one file in the corpus with **no `status`** —
> which is what it exists to be.)
>
> The fixtures are **schema-contract participants, not optional test data** (ruled 2026-07-12), so
> they migrate with everyone else — and that means Task 9 backfills their dates. This is the fixture
> tax the ruling deliberately accepted: *a fixture left unpinned would make the suite test an
> accidental mixed-version state.* **Backfill from the file's git history, never `date.today()`** —
> a fabricated `created` is exactly the manufactured provenance this arc keeps refusing.

**Files:**
- Modify: `science/model/src/science_model/entities.py` — `Entity.model_config` → `extra="allow"` (**D3.3**)
- Modify: `science/src/science_tool/graph/sources.py` — schema-first validation, gated on the pin (**D3.1/D3.2**)
- Create: `science/src/science_tool/migrate_hypothesis.py`
- Modify: `science/src/science_tool/entities_cli.py` (register `entity migrate-hypothesis`)
- Test: `science/model/tests/test_hypothesis_entity.py` — extend the battery to the **composed project profile**
- Test: `science/tests/test_migrate_hypothesis.py`
- Test: `science/tests/test_schema_first_load.py`

**Interfaces:**
- Consumes `status_inventory.inventory()` + **`adjudication_for(project_root)`** — *not* `load_adjudication(path)`.
  Absence of an adjudication file is **normal** (most projects need none), and `load_adjudication`
  raises on a missing path **by design**, so calling it directly would make every un-adjudicated
  project a crash. `adjudication_for` is the may-be-absent accessor; `load_adjudication` is the
  fail-loud reader behind it, for a path the author *did* write.
- Consumes **`entity_profiles.load_project_schema(project_root)`** — the project-COMPOSED profile, not
  the package-default `default_profile_for_kind`. ☠️ With the package default, **mm30's and
  evolution's extension fields are unknown keys**, so `unevaluatedProperties: false` rejects them and
  the migration refuses those two repos entirely — with an error blaming the files, for fields their
  project legitimately declares. Task 6b exists precisely so this composition is available; using the
  package default here would waste it and misread the failure as corpus corruption.
- **Adds no mapping logic.** The cross-tab lives in `status_inventory`, entirely and deliberately: a
  rule that lived here and not there would mean the inventory a human read and approved was not the
  migration that ran.

> ### The test subjects, in full. Revs 1–6 listed six; these are the ones they left out.
>
> | subject | why it is not optional |
> |---|---|
> | **the eight deletes** | one test per key is overkill; one parametrized test over `phase`/`belief_state`/`evidence_stance`/`tags`/`priority`/`role`/`promotion_criteria`/`domain` is not. A delete that silently doesn't fire leaves a key the mixin marks `false`, so the file fails *its own* schema at the end of Phase 1 — which is the good failure. Assert it anyway: the preflight's refusal must name the KEY, not just the file. |
| **the two renames** | value preserved **byte-for-byte**, old key gone, new key present — *and the migrated entity survives a load*, which is the property (1) above says the projection currently breaks. A rename test that only reads the file cannot see the delete-with-better-manners. |
> | **☠️ the `confidence` REFUSAL** | the migration must STOP on 3d-attention-bias's two files and name them. This is the one field where a plausible mechanical answer exists (`0.7` → a prior) and taking it would fabricate chronology. **A refusal with no test is a refusal that gets optimized away by the next implementer**, who will see two scalars and a `confidence_label` extension and think it obvious. |
> | **the fixture date backfill** | `created`/`updated` from **git history** (`git log --diff-filter=A --format=%as -- <path>`), never `date.today()`. Assert the backfilled value equals the file's real add-date; a test that only asserts *some* date passes for a fabricated one. |
> | **crash → rerun** | see the journal ruling below. Kill after file 1 of 2; assert the rerun COMPLETES and the corpus is byte-identical to an uninterrupted run. |
> | **the composed profile** | migrate an mm30-shaped file (with `identification`) and an evolution-shaped one (with `author_stated_evidence`); both must pass preflight. Against the package-default profile they cannot — which is the bug this catches. |

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_migrate_hypothesis.py
def test_refuses_everything_when_any_file_is_ambiguous(tmp_path) -> None:
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")     # deterministic
    _hyp(tmp_path, "0042-x", status="retired", phase="candidate")   # ambiguous
    with pytest.raises(MigrationRefused, match="0042-x"):
        migrate(tmp_path, apply=True)
    assert 'status: "proposed"' in (tmp_path / "entities/hypotheses/0001-a.md").read_text()


def test_an_adjudication_file_unblocks_it(tmp_path) -> None:
    # `complete` + `refuted` -- the shape the author RULED for natural-systems/0009 (Task 4). The
    # evidence spoke, so the verdict IS the closure reason and `closure_basis` stays absent.
    _hyp(tmp_path, "0009-d", status="retired", phase="candidate")
    (tmp_path / ".science").mkdir()
    (tmp_path / ".science/hypothesis-lifecycle.adjudication.yaml").write_text(
        "hypothesis:0009-d:\n  status: complete\n  verdict: refuted\n", encoding="utf-8")
    migrate(tmp_path, apply=True)
    t = (tmp_path / "entities/hypotheses/0009-d.md").read_text()
    assert 'status: "complete"' in t and 'verdict: "refuted"' in t


def test_a_project_with_NO_adjudication_file_migrates_fine(tmp_path) -> None:
    # `adjudication_for`, not `load_adjudication`. Absence is NORMAL -- most projects need none --
    # and the fail-loud reader would turn every un-adjudicated root into a crash.
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    migrate(tmp_path, apply=True)


def test_the_two_CONFIDENCE_files_are_REFUSED_not_converted(tmp_path) -> None:
    # ☠️ `0.7` names no proposition, stance, source, strength, or independence group. The plausible
    # mechanical answer -- call it a prior -- would relabel a POSTERIOR as something that preceded
    # the evidence. The tool stops; the author decomposes it into expert_judgment evidence lines.
    _hyp(tmp_path, "0001-a", status="proposed", phase="active", extra={"confidence": 0.7})
    with pytest.raises(MigrationRefused, match="confidence"):
        migrate(tmp_path, apply=True)


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

# The keys the migration REMOVES from frontmatter. `profile` is NOT among them: Task 2 §3 proved an
# authored `profile` is honored (sources.py:765-772 is fill-if-missing, not overwrite), reaches the
# graph as `sci:profile` (materialize.py:640), and drives `registration_state`
# (entities_inventory.py:195-199). Stripping it would DELETE a live semantic field from 3 files and
# silently change their registration state. An earlier draft of this plan had it here; that was the
# same "derived, so strip it" reflex that `_enrich_raw`'s fill-if-missing quietly disproves.
_DROPPED = ("phase", "disposition", "disposition_basis")

# Migrated, not dropped: their VALUES move (Task 10). Deleting them here would destroy content.
#   promoted_from -> origins   |   confidence -> author-written expert_judgment evidence lines


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
    _journal_clear(project_root)
    return [p for p, _ in planned]
```

> ### ☠️ "Re-running is safe and idempotent" was FALSE. It is the one claim here that could strand a repo.
>
> Revs 1–6 said: the pin is written last, so a crash leaves the project unpinned, and unpinned means
> not-schema-2, so just run it again. **The second step does not follow.** The rerun does not read the
> pin — it reads the FILES, through `status_inventory._classify`. And a file the crashed run already
> migrated is `status: draft` with **no `phase`**, so on the rerun `_classify` defaults the absent
> phase to `active`, finds `draft != active`, matches no branch, and falls through to the terminal /
> unknown arm: **"status 'draft' is terminal or unknown: adjudicate explicitly."**
>
> So a process killed after the first write leaves a corpus the migration **refuses to resume** and
> demands the author adjudicate — file by file, for files that are already correct. It does not
> corrupt anything (the refusal is real, and refusing is what this tool is for), but *"safe and
> idempotent"* is exactly the sentence that would have sent someone into that state trusting a rerun.
> An all-or-none writer whose crash recovery is "run it again" needs the rerun to actually work.
>
> **A JOURNAL, not a bigger claim.** Phase 2 writes `.science/hypothesis-migration.journal` **before**
> the first file and appends each path as it lands. Its presence means *a write pass was interrupted*:
>
> - **On a clean run** the journal is written, consumed, and deleted (`_journal_clear`), so its
>   absence is the normal state and carries no meaning.
> - **On a rerun with a journal present**, the tool does **not** re-plan from the files — the files no
>   longer speak the language the planner reads. It replays the journal's remaining entries from the
>   plan it already committed to disk, finishes the write, sets the pin, and clears the journal.
> - **If the journal disagrees with the corpus** (a file it names is gone, or its content is neither
>   the pre- nor the post-image), it **REFUSES** and says so. A half-migrated corpus is precisely the
>   two-meanings-of-`status` state this arc exists to eliminate, and guessing our way out of it would
>   be the compatibility layer D5 forbids, wearing a recovery hat.
>
> **Regression required — the one this plan shipped without:** kill the writer after file 1 of 2,
> assert the rerun COMPLETES (not refuses), and assert the resulting corpus is byte-identical to an
> uninterrupted run. A crash-recovery claim with no failure-injection test is a comment, not a
> property.

- [ ] **Step 4: The CLI surface — and it is Task 11's interface, not a convenience.**

```
science entity migrate-hypothesis                                  # dry run, this project
science entity migrate-hypothesis --apply                          # write + pin, this project
science entity migrate-hypothesis --preflight-all --manifest FILE  # render+validate EVERY root; write nothing
```

> `--preflight-all --manifest` is the only thing that makes the slice **atomic across 15
> repositories rather than merely ordered**. It reads the roster JSON that Task 11 Step 0 derives,
> renders and validates all 147 targets across all 18 roots, writes **nothing**, and exits non-zero
> if any root fails. Without it, Task 11's "no root is applied until every root's target has passed"
> is a sentence with no implementation, and the rollout degrades to per-root validate-then-write —
> which leaves `evolution`, the only root that can refute the extension composition, for last, after
> 14 repos are already written.

- [ ] **Step 5: Green** — both suites, ruff, pyright.

- [ ] **Step 6: Commit.**

---

### Task 10: Consumers — and **only** the hypothesis branch

> ### ✅ DONE — `39d98e9f` (the write boundary). Task 8's commit carried the vocabulary re-pointing.
>
> **THREE DEPARTURES FROM WHAT THIS TASK PRESCRIBED**, and Tasks 11–12 depend on each:
>
> 1. **The schema check is gated on the PIN, not only on the kind.** This task said
>    `_schema_validate_or_raise` "skips kinds not yet in `PROJECT_MIXIN_NAMES`" and said nothing
>    about the project. But Task 9 ruled the authored pin the sole authority on whether a project
>    speaks schema 2 — so a writer that decided it on its own would be a second authority for the
>    one fact this arc keeps collapsing. Unpinned, the schema half is silent: enforcing the 2.0
>    mixin on a project the migration has not reached would reject `--title` over a `phase:` key the
>    migration is coming for. **Consequence: the schema half of this boundary is INERT on the real
>    corpus until Task 11 pins each project.** Both halves now ask `load_project_schema_if_pinned`.
>
> 2. **The LINEAGE check is deliberately NOT pin-gated.** `superseded` meant `superseded` in the old
>    vocabulary too, so a dangling successor is authorable in an unmigrated project *today* — which
>    is exactly the corpus that most needs the guard. Gating it on the pin would arm it only for the
>    projects already made safe. It is live now, on all 18 roots.
>
> 3. **`--resynthesized-into` was added, and without it this task shipped decoration.** The
>    parameter this task put on `edit_entity` had **no production caller**: zero uses across the
>    corpus, and no CLI flag: the dangling-successor rule would have been enforced only against its
>    own test. The schema discharges `superseded` with any of `superseded_by` (DERIVED, unauthorable
>    — correctly), `closure_basis`, or `resynthesized_into`; with no flag for the third, a **split
>    supersession was a state the schema admitted and no writer in the toolkit could produce.**
>
> Two more things this task did not foresee:
>
> - `SCHEMA_ENFORCED_KINDS` (Task 9) is **deleted**. It was a second hand-maintained copy of
>   `PROJECT_MIXIN_NAMES` — which is the migration slice list *and* gates schema strictness, so a
>   kind present in one and absent from the other is checked against a profile that admits anything.
>   **Task 12's ratchet now has ONE list to widen, in the model.**
> - `render_entity_frontmatter_updates` is a **second entity writer**: arbitrary `updates` mapping,
>   no schema check, no resolution check, and it writes `superseded_by` / `resynthesized_into`
>   outright. Not a hole today — both callers operate on **propositions**, which have no project
>   mixin — but it is pinned by an AST guard, and **the proposition slice must close it**.

> ### ⚠️ HALF OF THIS TASK ALREADY LANDED, WITH TASK 8. Read this before starting.
>
> Task 8's descriptor change is **global** — `default_profile_for_kind` is not per-project — so the
> instant it lands, every consumer reading the old vocabulary is wrong. There is no green commit
> containing Task 8 alone, which is exactly what Task 8's Step 4 says ("run Task 10's edits together
> with this task's if the suite is red"). It was red. So the **vocabulary re-pointing** shipped in
> Task 8's commit, and what remains here is Task 10's **own new capability**.
>
> **DONE (in Task 8's commit):**
> - `hypotheses_cli.py` — `--phase` deleted, `--status draft|active`, promotion-criteria on `draft`
> - `annotation/promote.py` — `fields["phase"] = "candidate"` → `fields["status"] = "draft"`
> - `validate/checks/hypotheses.py` — the `phase` shape check **deleted** (the mixin forbids the key
>   outright: `"phase": false`. A shape check for a field the schema refuses is a second authority.)
> - `graph/materialize.py` — `sci:disposition` / `sci:dispositionBasis` **deleted**, with their model
>   fields, in the same commit as their only reader
> - `graph/attention.py` — terminal exclusion and `list_rehoming_debt` now read the LIFECYCLE
> - `validate/checks/dataset_capabilities.py` — `is_demand_closed(kind=, status=, verdict=)`
> - `commands/add-hypothesis.md`, `commands/big-picture.md` (+ regenerated `codex-skills/`)
> - `tests/test_hypothesis_consumers.py` — the `is_demand_closed` / `DEBT_QUESTION_STATUSES` half
>
> **STILL OPEN (this task's real work):** the **write boundary**. `entities_cli.py` gains
> `--verdict` / `--closure-basis`; `_prepare_write` gains schema validation and the
> `check_resolution` guard; `_validate_status`'s raw `KeyError` is fixed; and the rest of
> `test_hypothesis_consumers.py` (the `edit_entity` lifecycle-transition tests, the `_prepare_write`
> / `_commit_write` call-site guards, the corrupted-inverse test) is written.
>
> ☠️ **`is_demand_closed` reads the VERDICT for a hypothesis and the STATUS for a question, and that
> asymmetry is deliberate.** The question slice has not run. Do not "tidy" it into one rule — doing so
> silently reopens every answered question in the corpus. `DEBT_QUESTION_STATUSES` stays frozen.

**Files:**
- `science/src/science_tool/hypotheses_cli.py:28-34,62-64` — `--phase` → `--status`; the `promotion-criteria` section now triggers on `status == "draft"`
- `science/src/science_tool/entities_cli.py:94-125` — add `--verdict` and `--closure-basis`.
  **NOT `--superseded-by`.** That field is **derived** (Task 7a: inverted from the canonical
  `sci:supersedes` edge by `mark_superseded`). An author flag for it would recreate the second
  authored spelling rev 10 deleted — a user could write a resolvable `superseded_by` with **no
  canonical edge behind it**, and schema *and* `check_resolution` would both report green over a
  supersession grounded in nothing. **And no Python caller can do it either:** the derived writer
  (`consolidation._prepare_supersession`) takes the *graph*, not a lineage string (Task 7a).
- `science/src/science_tool/entities.py` — put schema validation and the `check_resolution` guard
  **inside `_prepare_write`** (the boundary Task 7a split out): a terminal transition with a
  dangling successor must fail **before a byte is written**. Task 7 could not host this — there was
  no write boundary to hang it on. **Both entry points inherit it**, because both go through
  `_prepare_write`: `edit_entity` (authored fields) and `_prepare_supersession` (the derived
  inverse). A boundary that governs only the path nobody was going to corrupt is decoration.
- `science/src/science_tool/entities.py:1377-1379` (`_validate_status`) — also fix its raw `KeyError` (it indexes `_STATUS_VALUES[kind]` and ignores project-local manifests, unlike `valid_statuses`)
- `science/src/science_tool/graph/materialize.py` — **delete** `sci:disposition` (its emission of
  `sci:verdict` landed in **Task 7**, which needed it to make the verdict check observable). The
  deletion belongs *here* because `attention.py` below is its only reader, and predicate and reader
  must go in one commit.
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

- [x] **Step 1: Write the failing tests**

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


def test_edit_entity_refuses_a_DANGLING_successor(tmp_project) -> None:
    # MOVED HERE FROM TASK 7, which could not host it: the write boundary did not exist.
    # `check_resolution` (Task 7) is the checker; this is its write-boundary call site.
    #
    # THE LINEAGE FIELD HERE IS `resynthesized_into`, NOT `superseded_by` -- and that is not a
    # detail. `superseded_by` is DERIVED (Task 7a) and there is no parameter, on any writer, that
    # could carry a dangling one to this boundary: `_prepare_supersession` reads it from
    # `graph.superseder_by_id`, i.e. from an ADMITTED canonical edge.
    #
    # (An earlier draft justified this with "the builder drops edges to unknown ids, so the inverse
    # always resolves." That was true, and it was a BUG -- the invariant held because the dangling
    # canonical edge was silently deleted. Task 7a stopped deleting it: an unresolved target is now
    # REPORTED and BLOCKS apply. The conclusion here survives, but on a completely different footing:
    # the inverse cannot dangle because the edge behind it was ADMITTED, not because a dangling edge
    # was thrown away unseen.)
    #
    # `resynthesized_into` has no canonical relation behind it -- it is genuinely authored -- so it
    # is the one lineage field a human can dangle, and the only one this guard can be written
    # against. A guard aimed at the unreachable case is decoration.
    with pytest.raises(EntityCommandError, match="9999-nope"):
        edit_entity(tmp_project, "hypothesis:0001-x", status="superseded",
                    resynthesized_into=["hypothesis:9999-nope"])


def _corrupt(project_root: Path, entity_id: str, **fields: object) -> None:
    """Hand-edit an entity's frontmatter, BYPASSING every writer.

    It has to bypass them -- that is the state under test. `edit_entity` would refuse most of these,
    which is the point: this simulates a human with a text editor, or a file that predates a rule.
    """
    location = find_entity(project_root, entity_id)
    fm = dict(location.frontmatter) | fields
    location.path.write_text(
        f"---\n{yaml.safe_dump(fm, sort_keys=False)}---\n\n{location.body}", encoding="utf-8"
    )


def test_no_writer_can_be_HANDED_a_groundless_lineage(tmp_project) -> None:
    # An earlier draft of this test called `stamp_supersession(ref, superseded_by="hypothesis:9999-
    # nope")` and asserted the boundary refused it. It PASSED -- and it was the bug. To assert the
    # guard, the test had to PERFORM the violation, which was only possible because the signature
    # accepted the derived fact AS CALLER INPUT. A resolvable id with no canonical edge behind it
    # passes schema AND `check_resolution`, and the supersession is grounded in nothing.
    #
    # THE NEXT DRAFT WAS WORSE. It asserted `"superseded_by" not in signature(edit_entity).parameters`
    # -- while `edit_entity` took `**fields` and forwarded to a PUBLIC `prepare_entity_write` that
    # declared `superseded_by` outright. Both calls below worked. The assertion passed ANYWAY, because
    # the absence of a named parameter is exactly what a VAR_KEYWORD signature guarantees whether or
    # not the field is reachable. It was ANTI-INFORMATIVE: it passed BECAUSE the hole was open.
    #
    # So this test does what the earlier one only claimed: it CALLS the authored surface with the
    # derived field and requires the call itself to be impossible. And it forbids the VAR_KEYWORD that
    # would silently un-assert everything below it.
    with pytest.raises(TypeError):
        edit_entity(tmp_project, "hypothesis:0001-x",       # type: ignore[call-arg]
                    superseded_by="hypothesis:0002-y")      # RESOLVABLE. Still groundless.

    for fn in (edit_entity, _prepare_supersession):
        params = inspect.signature(fn).parameters
        assert "superseded_by" not in params
        assert not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()), (
            f"{fn.__name__} grew a **kwargs -- which reopens the door AND makes the assertion "
            f"above vacuous. The unrestricted mechanism is `entities._prepare_write`, and it is "
            f"private for exactly this reason."
        )


def _call_sites(target: str) -> set[tuple[str, str]]:
    """Every (module, enclosing function) that CALLS `target`, by AST.

    An earlier draft grepped for the substring `_prepare_write` and asserted the set of files
    containing it. That proves nothing it claims: a docstring mentioning the name counts as a
    caller, a module that imports it and never calls it counts as a caller, and -- the reason it
    actually fails -- a SECOND function inside consolidation.py calling it does NOT count as
    anything, because the file was already in the set. The guard could not see the violation it
    exists to see. Match the call, and name the caller.
    """
    sites: set[tuple[str, str]] = set()
    for path in (SRC / "science_tool").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for enclosing in ast.walk(tree):
            if not isinstance(enclosing, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(enclosing):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else (
                    fn.attr if isinstance(fn, ast.Attribute) else None)
                if name == target:
                    sites.add((path.name, enclosing.name))
    return sites


def test_the_unrestricted_MECHANISM_has_exactly_the_call_sites_we_sanctioned() -> None:
    # `_prepare_write(project_root, ref, fields: Mapping)` CAN set `superseded_by` -- it is the
    # mechanism, and it has to be able to. The guarantee is not that it refuses; it is that the ONLY
    # caller that supplies that key is the one that DERIVES it from an admitted edge. So pin the call
    # sites by name and by COUNT: a third one is how this arrangement would quietly stop being true.
    assert _call_sites("_prepare_write") == {
        ("entities.py", "edit_entity"),                    # authored -- cannot express the field
        ("consolidation.py", "_prepare_supersession"),     # derived  -- reads it off the graph
    }


def test_the_COMMIT_half_has_exactly_the_call_sites_we_sanctioned() -> None:
    # `_commit_write` does not repeat schema or resolution validation -- by contract. It DOES
    # authenticate the concrete token and its payload at the write boundary. `mark_superseded` is a
    # sanctioned caller because it commits a batch that `_prepare_supersession` prepared and
    # `_prepare_write` validated.
    assert _call_sites("_commit_write") == {
        ("entities.py", "edit_entity"),
        ("consolidation.py", "mark_superseded"),
    }


def test_a_CORRUPTED_inverse_is_caught_by_the_net_that_MATCHES_ITS_FAILURE(tmp_project) -> None:
    # And this is where the deleted test's real subject went. A hand-edited `superseded_by` is NOT
    # caught at the write boundary -- nothing can hand one to a writer, so no writer ever sees it.
    # Saying "the boundary catches it" would be false. THREE things catch it, and WHICH ONE depends
    # on how it is wrong -- a distinction an earlier revision got wrong by asserting `check_resolution`
    # covers the groundless case (it does not: it sees REFERENCES, and a groundless inverse RESOLVES):
    #
    #   1. STALE (an edge exists, pointing elsewhere) -> `mark_superseded` RECONCILES it. `to_repair`.
    #   2. DANGLING (the id resolves to nothing)      -> `check_resolution` (Task 7). Validate WARN.
    #   3. GROUNDLESS (resolves; NO edge behind it)   -> `unbacked_inverses` (Task 7a). Blocks apply.
    #
    # This test pins row 1. Rows 2 and 3 are pinned in test_consolidation_mark_superseded.py, on the
    # kind that can carry them today.
    _corrupt(tmp_project, "hypothesis:0001-x", status="superseded",
             superseded_by="hypothesis:9999-nope")
    _corrupt(tmp_project, "hypothesis:0002-y",
             relations=[{"predicate": "sci:supersedes", "target": "hypothesis:0001-x"}])

    report = mark_superseded(tmp_project, apply=True)

    assert report["repaired"] == ["hypothesis:0001-x"]
    fm = read_frontmatter(tmp_project / "entities/hypotheses/0001-x.md")
    assert fm["superseded_by"] == "hypothesis:0002-y"     # the EDGE won, not the hand edit
```

- [x] **Step 2: Run and fail.**

- [x] **Step 3: Implement.** `dataset_capabilities` — change **only** the hypothesis branch:

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

`_prepare_write` — the generic lifecycle boundary (D4). **Task 7a split it out of `edit_entity`; this
task is what puts the enforcement inside it.** It is **private**, it takes a **mapping**, and it has
**no `**kwargs`**. Both entry points go through it, so neither can be validated after the fact:

```python
def _prepare_write(project_root: Path, ref: str, fields: Mapping[str, object]) -> _PreparedWrite:
    """PRIVATE mechanism. Merge, render, validate. Writes NOTHING."""
    project_root = project_root.resolve()
    _reject_if_archived(project_root, ref)
    location = find_entity(project_root, ref)
    frontmatter = dict(location.frontmatter)

    for key in ("title", "status", "verdict", "closure_basis", "resynthesized_into",
                "superseded_by"):          # <- settable HERE; see the policy table below for by WHOM
        if fields.get(key) is not None:
            frontmatter[key] = fields[key]
    for key in ("related", "source_refs"):
        if fields.get(key):
            frontmatter[key] = _append_unique_string_values(frontmatter.get(key), fields[key])
    frontmatter["updated"] = (fields.get("updated") or fields.get("today")
                              or date.today()).isoformat()

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
    # The seal is applied HERE and nowhere else. It is not a field a caller fills in; it is this
    # function's signature ON THIS TEXT, FOR THIS PATH -- the assertion that everything above actually
    # ran, against exactly these bytes.
    return _PreparedWrite(entity_id=location.entity_id, path=location.path,
                          text=text, warnings=tuple(warnings),
                          seal=_seal(location.entity_id, location.path, text))
```

> **Why `superseded_by` is settable HERE and expressible on neither writer.**
> `_prepare_write` is the shared *mechanism* — it renders and validates whatever frontmatter it is
> given, and a mechanism that could not set a derived field would be useless to the thing that derives
> it. The **policy** is enforced by the two functions that call it, and by the fact that **they are
> the only two** (`test_the_unrestricted_mechanism_has_exactly_ONE_caller_outside_entities`):
>
> | writer | `superseded_by` | who supplies it |
> |---|---|---|
> | `edit_entity` (authored surface, reached by `science entity edit`) | **not a parameter, and no `**kwargs`** | nobody — the call does not typecheck and does not run |
> | `consolidation._prepare_supersession(project_root, graph, member)` | **not a parameter** | `graph.superseder_by_id[member]` — an admitted canonical edge |
>
> So the derived field has exactly one source in the entire codebase: the inversion of an edge the
> builder admitted. There is no flag for it and no argument for it — and **`_prepare_write` is private
> precisely so that "no argument for it" cannot be undone by someone reaching past the authored
> surface.** An earlier draft made this function *public* and gave `edit_entity` a `**fields`
> passthrough; both then accepted `superseded_by` directly, and the signature test that was supposed
> to catch it passed, because `**kwargs` *guarantees* the named parameter is absent. That test now
> **calls** both interfaces and requires the call to fail.

```python
def edit_entity(
    project_root: Path, ref: str, *,
    title: str | None = None, status: str | None = None,
    verdict: str | None = None, closure_basis: str | None = None,
    resynthesized_into: list[str] | None = None,   # AUTHORED -- no canonical relation behind it
    # NO `superseded_by`, and NO **kwargs. The field is DERIVED (Task 7a): an authored spelling --
    # or a smuggled one -- lets a caller mint a resolvable lineage with no canonical edge behind it,
    # which passes schema AND `check_resolution` and is superseded according to nothing.
    related: list[str] | None = None, source_refs: list[str] | None = None,
    updated: date | None = None, today: date | None = None,
) -> EntityWriteResult:
    """The AUTHORED-edit surface. Prepare, then commit."""
    return _commit_write(_prepare_write(project_root, ref, {
        "title": title, "status": status, "verdict": verdict, "closure_basis": closure_basis,
        "resynthesized_into": resynthesized_into, "related": related, "source_refs": source_refs,
        "updated": updated, "today": today,
    }))


def _commit_write(prepared: _PreparedWrite) -> EntityWriteResult:
    """PRIVATE. Authenticate, then atomically replace; schema and resolution were settled in prepare.

    The `isinstance` check is required because Python does not enforce the annotation at runtime.
    The HMAC check is repeated HERE because this is the trust boundary: `__post_init__` proves only
    what was true when the value was constructed, not what is true when its bytes are consumed.
    """
    if not isinstance(prepared, _PreparedWrite):
        raise TypeError("a prepared write must be earned from _prepare_write")
    if not hmac.compare_digest(
        prepared.seal, _seal(prepared.entity_id, prepared.path, prepared.text)
    ):
        raise TypeError("prepared-write seal does not cover the bytes and path being committed")
    _atomic_replace_text(prepared.path, prepared.text)
    return EntityWriteResult(entity_id=prepared.entity_id, path=prepared.path,
                             warnings=list(prepared.warnings))
```

where `_schema_validate_or_raise` derives the profile via `default_profile_for_kind`, **skips
kinds not yet in `PROJECT_MIXIN_NAMES`** (an explicit "not migrated", not a fallback), and
re-raises `EntityValidationError` as `EntityCommandError`.

**The derived writer inherits all of this for free** — `consolidation._prepare_supersession` calls
`_prepare_write`, so the same `find_entity`, the same `_schema_validate_or_raise`, the same
`_resolution_check_or_raise`. One gate, two entry points, and the enforcement lives in the half that
**writes nothing** — which is also what lets `mark_superseded` prepare every planned write before
committing any of them, and so keep the all-or-none promise it makes (Task 7a).

- [x] **Step 4: Green — everything, both packages, ruff, pyright.**

- [x] **Step 5: Commit.**

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

  **`--project "$WT"` and the import assertion are mandatory here too** (Global constraint 0):
  `field_inventory` is *this branch's* instrument, and a bare `uv run` resolves a toolkit that does
  not have it — or, worse, an older one that does and counts differently.

> **☠️ THE FOUR TOOLKIT-OWNED ROOTS MUST RESOLVE TO THIS WORKTREE, NEVER THE MAIN CHECKOUT.** `meta`
> and the three `tests/fixtures/**` roots live INSIDE `~/d/science`, and this branch's changes to them
> — the adjudication artifact, the pinned/canary fixtures, the migrated frontmatter — exist only in
> this worktree. A `~/d/**/science.yaml` glob that skips `.claude`/`.worktrees` does not omit these
> four; it finds them in the MAIN checkout, which lacks all of it, and preflight then refuses
> `commons_mm30_canary` for a missing adjudication file that is right here. So the roster is built in
> **two disjoint halves**: the 14 EXTERNAL roots from `~/d` with the entire `~/d/science` tree
> excluded, and the 4 TOOLKIT-OWNED roots enumerated from the worktree explicitly. 14 + 4 = 18.

```bash
WT=$(realpath ~/d/science/.claude/worktrees/instrument-result/science)

uv run --project "$WT" python - "$WT" <<'PY'
import json, pathlib, subprocess, sys
from pathlib import Path

import science_tool
# EXACT path equality (Global constraint 0). A substring test is fail-open: `.worktrees` admits any
# OTHER worktree, and `science/src` admits the main checkout -- the two nearest wrong answers.
_got = pathlib.Path(science_tool.__file__).resolve().parent
_want = (Path(sys.argv[1]) / "src" / "science_tool").resolve()
if _got != _want:
    sys.exit(f"WRONG TOOLKIT\n  loaded:   {_got}\n  expected: {_want}")

from science_tool.field_inventory import field_inventory

D = Path.home() / "d"
WT = Path(sys.argv[1]).resolve()          # ~/d/science/.claude/worktrees/<name>/science
WT_REPO = WT.parent                       # the worktree checkout root (holds meta/ and tests/)
SCIENCE = (D / "science").resolve()       # the toolkit repo -- EVERY checkout of it is excluded below

# HALF 1: the 14 external roots. Exclude the whole `~/d/science` subtree (main checkout AND every
# worktree under it), so the four toolkit-owned roots come ONLY from HALF 2, at the worktree.
SKIP = {".venv", ".git", ".claude", ".worktrees", "node_modules", "templates"}
external = {
    p.parent.resolve()                    # .resolve() collapses the ~/d/r/* symlinks
    for p in D.glob("**/science.yaml")
    if not any(s in SKIP for s in p.parts) and "--" not in p.parent.name
    and SCIENCE not in p.resolve().parents  # <- the fix: no root inside the toolkit repo
}

# HALF 2: the four toolkit-owned roots, taken from THIS worktree by exact path -- not discovered by a
# glob that could bind them to the main checkout. `meta`, plus the three fixture projects.
toolkit_owned = [
    WT_REPO / "meta",
    WT / "tests" / "fixtures" / "spec_y_kitchen_sink",
    WT / "tests" / "fixtures" / "big_picture" / "minimal_project",
    WT / "tests" / "fixtures" / "commons_mm30_canary" / "project",
]
for r in toolkit_owned:
    if not (r / "science.yaml").is_file():
        sys.exit(f"MISSING TOOLKIT-OWNED ROOT: {r}")

roots = sorted(external | {r.resolve() for r in toolkit_owned})
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
# The four toolkit-owned roots share ONE repo -- this worktree -- so a group-by-repo commit in Step 1
# must key on `git rev-parse --show-toplevel`, never on the root path.
wt_top = subprocess.run(["git", "-C", str(WT_REPO), "rev-parse", "--show-toplevel"],
                        capture_output=True, text=True, check=True).stdout.strip()
owned_here = [m for m in manifest if m["repo"] == wt_top]
print(f"{len(manifest)} roots, {sum(m['n'] for m in manifest)} hypotheses, {len(repos)} git repos")
print(f"  toolkit-owned in THIS worktree ({wt_top}): {[m['slug'] for m in owned_here]}")
PY
```

Expect **18 roots / 147 hypotheses / 15 git repos** as of 2026-07-12 — 14 external plus the four
toolkit-owned (`meta`, `spec_y_kitchen_sink`, `big_picture/minimal_project`,
`commons_mm30_canary/project`), all four resolving inside this worktree's checkout.

> **The gate is set equality on `(root, n)` — not the totals.** `18/147` is satisfiable while a
> root silently disappears and another gains the same count. Snapshot the manifest **once**, here,
> and require **exact equality** against a freshly derived one immediately before *apply* (Step 1)
> and again before the *ratchet* (Task 12). Any diff ⇒ the corpus moved under a certification that
> was measured against exactly these 147 files. **Stop and re-certify; do not reconcile in place.**

- [ ] **Step 1: Two-phase preflight over ALL 147 targets — render and validate everything, then
  write.** No root is applied until every root's rendered target has passed. This is what makes the
  slice atomic across 15 repositories rather than merely ordered.

```bash
uv run --project "$WT" science entity migrate-hypothesis \
    --preflight-all --manifest /tmp/claude-1000/roster.json
```

> **Bare `uv run` here would preflight the corpus against the PINNED toolkit** — one with no
> `mixin-hypothesis-1.0` and no `entity_extensions` — which cannot fail the way this gate needs to
> fail, and would certify all 147 files by **not looking at them**. Global constraint 0.

- **Preflight must include `cancer/mechanisms/evolution`.** It is the only root where Task 2b's
  deletion and Task 6b's **`evolution.provenance`** extension actually bite — and the only root
  where the migration *writes a key that did not exist* (`author_stated_evidence` →
  `source_stated_evidence`, 13 files). **This is also where Task 6b's deferred corpus gate is
  finally discharged**, on both projects at once: the extensions were proved correct at unit level
  in 6b, but *these files validate* is a claim about migrated frontmatter, and this is the first
  point in the plan where migrated frontmatter exists.
- **With a green all-corpus preflight, apply order is free** — take smallest-first
  (`pre-cancer` (1) …) so a surprise is cheapest.
- **If you ever fall back to per-root validate-then-write, apply `evolution` FIRST.** Ordering by
  size would leave the most refutation-capable corpus for last, after 14 repos are already written.

For each root (order per above):

> **Two things every command here gets wrong if copied naively.** `graph build` has **no `--output`**
> — it writes `knowledge/graph.trig` **in place**, so a snapshot is a `cp` and the working tree must
> be restored afterwards. And a bare `uv run` inside a consumer resolves the toolkit from its
> **pinned public Git revision** (`science = { git = "…/science.git" }` in the consumer's
> `pyproject.toml`, revision locked in its `uv.lock`) — *not* from any local checkout — so it would
> migrate and diff using toolkit code that **does not contain this plan**, and would not error while
> doing it. `--project "$WT"` plus the import assertion is Global constraint 0. Both were live
> defects in this document.

```bash
set -euo pipefail                                    # the ONLY thing that stops a failed `graph
                                                     # build` from being followed by a `cp` of the
                                                     # STALE committed graph -- which diffs clean,
                                                     # exactly like a root that was really untouched

WT=$(realpath ~/d/science/.claude/worktrees/instrument-result/science)   # see Global constraint 0
SLUG=$(...)                                          # from the manifest -- NOT basename $PWD:
                                                     # science/meta and health/meta both basename
                                                     # to "meta", and ~/d/r/mm30 is a SYMLINK to
                                                     # multiple-myeloma -- resolve() or double-count
cd "$ROOT"
git status --short knowledge/                        # clean, or the "before" is somebody else's
uv run --project "$WT" science graph build --local-only
cp knowledge/graph.trig /tmp/claude-1000/before-$SLUG.trig
uv run --project "$WT" science entity status-inventory   # 0 refused, or adjudicate first
uv run --project "$WT" science entity migrate-hypothesis --apply   # sets entity_schema_version: 2
uv run --project "$WT" science graph build --local-only
cp knowledge/graph.trig /tmp/claude-1000/after-$SLUG.trig
uv run --project "$WT" science validate            # MUST exit 0 -- under `set -e` a nonzero exit
                                                   # ABORTS the root rather than printing itself
```

> **A root whose graph cannot BUILD cannot be gated.** `protein-landscape` fails
> `graph build` today (`unresolved references: question:0004-mega-cluster-split aliases -> q04`),
> pre-existing and reproducible on main. Fix the alias, or drop the root and re-certify the roster at
> 17 — **but do not let the `graph build` step fail and carry on**, because a skipped diff is
> indistinguishable from a clean one, and this whole gate exists to tell those two apart.

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
WT=$(realpath ~/d/science/.claude/worktrees/instrument-result/science)

uv run --project "$WT" python - "$WT" <<'PY'
import json, pathlib, subprocess, sys
from pathlib import Path

WT = Path(sys.argv[1]).resolve()
WANT = (WT / "src" / "science_tool").resolve()      # the EXACT path, not a substring

def _toolkit_of(root: str) -> Path:
    """Which science_tool does a run in `root` actually load? ASSERT it; never assume."""
    r = subprocess.run(
        ["uv", "run", "--project", str(WT), "python", "-c",
         "import pathlib, science_tool; print(pathlib.Path(science_tool.__file__).resolve().parent)"],
        cwd=root, capture_output=True, text=True, check=True,
    )
    return Path(r.stdout.strip())

manifest = json.loads(Path("/tmp/claude-1000/roster.json").read_text())
failed = []
for m in manifest:
    got = _toolkit_of(m["root"])
    if got != WANT:
        # Anything else is the pinned PUBLIC revision, the main checkout, or a STALE worktree from
        # another branch -- none of which contain this plan, so none of them can fail the way this
        # gate needs to fail. They would certify the corpus by not looking at it.
        sys.exit(f"WRONG TOOLKIT in {m['root']}\n  loaded:   {got}\n  expected: {WANT}")
    r = subprocess.run(["uv", "run", "--project", str(WT), "science", "validate"],
                       cwd=m["root"], capture_output=True)
    print(f"exit={r.returncode}  {m['root']}")
    if r.returncode:
        failed.append(m["root"])
if failed:
    sys.exit(f"{len(failed)} root(s) failed validate: {failed}")
PY
cd ~/d/science/science && uv run --frozen pytest -q   # the 3 fixture roots live in THIS repo
```
**Every root exits 0, and our own suite is green.** This is the step whose absence caused the
original incident — and rev 1–3 would have run it over 58% of the corpus and called it clean.

> **The loop must ASSERT the toolkit and EXIT NONZERO.** The earlier form ran bare
> `uv run science validate` — the **pinned public revision**, which contains none of this plan — and
> merely *printed* each exit code into a scroll nobody diffs. A run that validates 147 files with a
> toolkit that has no `mixin-hypothesis-1.0` prints `exit=0` eighteen times and has **checked
> nothing.** Assert the import path per root, and fail the step, not the reader's attention.

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

**Files:**
- Create: `science/src/science_tool/validate/kind_severity.py` — **the shared interface.**
- Modify: `science/src/science_tool/validate/checks/hypotheses.py` — **both** kind-level emitters
  (`hypothesis.status-vocabulary` **and** `hypothesis.dangling-lineage`) call it.
- Modify: `science/src/science_tool/validate/checks/supersession.py` (Task 7a) — the **third**
  kind-level emitter. It ships with a hard-coded `Severity.WARN` and a comment pointing here; replace
  it with `severity_for_kind(kind)`.
- Modify: `science/src/science_tool/validate/gates.py` — add `hypothesis.dangling-lineage` **and
  `hypothesis.unbacked-inverse`** to `_TIER_RULES["hygiene"]`.
- Test: `science/tests/test_kind_severity.py`, `science/tests/test_resolution_wiring.py`

**Interfaces:**
- Produces: `severity_for_kind(kind: str) -> Severity`; `_CERTIFIED_KINDS: frozenset[str]`

> **`_severity` was a private local, and it certified exactly one of the three rules that need it.**
> Rev 1 defined it inside `checks/hypotheses.py` for `status-vocabulary`, while Task 7 emitted
> `hypothesis.dangling-lineage` at a **hard-coded** WARN and promised — in a comment — that "ERROR
> is Task 12's ratchet, per kind." **Task 12 never touched it.** The kind would have been certified
> and the lineage violation would have stayed WARN forever, with the plan asserting otherwise in
> two places. A promise kept in prose by neither module is not a ratchet.
>
> **Task 7a's `unbacked-inverse` was the same promise, made a second time**, and it is listed above
> so that it is *this task's file*, not a comment's aspiration. Three kind-level emitters; one
> severity function; one test per flip.
>
> So severity for **kind-level** rules is one named function in one module, and all three emitters
> call it. (**Rule**-level ratchets — `verdict.missing-basis` — are a different axis and deliberately
> do **not** consult it; see the independence test below and the deferred-ratchet box.)

> #### Why the gate can only take KIND-SCOPED rule names
>
> `gated_findings` filters on `Result.rule` and **never reads severity** (`gates.py:59-62`). So
> whatever goes into `_TIER_RULES["hygiene"]` fails the build for *every* finding carrying that rule
> name — WARN ones included. A generic `supersession.unbacked-inverse` in the tier would therefore
> gate `report`, `question`, and every other **uncertified** kind the instant `hypothesis` earned its
> promotion: a ratchet on one kind silently becoming a ratchet on all of them.
>
> That is the status-vocabulary incident's shape exactly — severity graded on an axis that does not
> track certification. So the rule names are kind-scoped (`hypothesis.unbacked-inverse`), the gate
> lists the certified kind's name only, and an uncertified kind's finding stays a WARN that gates
> nothing. **The `_CERTIFIED_KINDS` set and the `hygiene` tier advance together, one kind at a time.**

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_kind_severity.py
from science_tool.validate.kind_severity import severity_for_kind


def test_severity_is_a_property_of_the_KIND() -> None:
    # The original incident: severity graded on `layout_version >= 3`. All five projects were
    # v3, so the gate graded NOTHING and 472 entities errored the moment the check landed.
    assert severity_for_kind("hypothesis") is Severity.ERROR   # sources AND consumers certified
    assert severity_for_kind("report") is Severity.WARN        # not migrated
    assert severity_for_kind("question") is Severity.WARN
```

```python
# science/tests/test_resolution_wiring.py -- the flip this task actually OWES.
def test_dangling_lineage_FLIPS_to_error_with_the_kind(tmp_project) -> None:
    # Task 7 pinned this finding at "warn" and pointed HERE. If `checks/hypotheses.py` still
    # hard-codes WARN, this fails -- which is the only thing that makes Task 7's comment true.
    write_hypothesis(tmp_project, "0001-x", status="superseded",
                     extra={"superseded_by": "hypothesis:9999-nope"})
    findings = [r for r in run_validate(tmp_project) if r.rule == "hypothesis.dangling-lineage"]

    assert [f.severity for f in findings] == ["error"]


def test_dangling_lineage_is_GATED_once_it_is_an_error(tmp_project) -> None:
    # Severity without a tier fails nobody's build. Task 7 pinned its ABSENCE from `hygiene`;
    # this task inverts it, and the inversion is the deliverable.
    from science_tool.validate.gates import cumulative_rules

    assert "hypothesis.dangling-lineage" in cumulative_rules("hygiene")


def test_unbacked_inverse_FLIPS_to_error_with_the_kind(tmp_project) -> None:
    # THE SECOND STRANDED PROMISE. Task 7a ships `checks/supersession.py` with a hard-coded
    # `Severity.WARN` and a comment pointing here -- which is precisely what Task 7 did with
    # `dangling-lineage`, and precisely what left it WARN forever. This test is the thing that makes
    # the comment true, and it is red until the emitter calls `severity_for_kind`.
    write_hypothesis(tmp_project, "0001-x", status="superseded",
                     extra={"superseded_by": "hypothesis:0002-y"})   # RESOLVABLE. No edge behind it.
    write_hypothesis(tmp_project, "0002-y", status="active")
    findings = [r for r in run_validate(tmp_project) if r.rule == "hypothesis.unbacked-inverse"]

    assert [f.severity for f in findings] == ["error"]


def test_unbacked_inverse_stays_WARN_for_an_UNCERTIFIED_kind(tmp_project) -> None:
    # THE CONTROL, and the reason the rule name is kind-scoped. `interpretation` is NOT in
    # `_CERTIFIED_KINDS`: its sources and consumers have not been through the D5 slice. The same
    # defect, on that kind, must stay a WARN -- and must NOT be gated.
    #
    # Emit a single generic `supersession.unbacked-inverse` instead and this is unreachable: the gate
    # reads rule names only (gates.py:59-62), so promoting `hypothesis` would have promoted every
    # kind that shares the name. Severity graded on an axis that does not track certification is the
    # status-vocabulary incident, restaged.
    from science_tool.validate.gates import cumulative_rules

    write_interpretation(tmp_project, "i-v1", status="superseded",
                         extra={"superseded_by": "interpretation:i-v2"})
    write_interpretation(tmp_project, "i-v2", status="active")
    findings = [r for r in run_validate(tmp_project) if r.rule == "interpretation.unbacked-inverse"]

    assert [f.severity for f in findings] == ["warn"]
    assert "interpretation.unbacked-inverse" not in cumulative_rules("hygiene")
    assert "hypothesis.unbacked-inverse" in cumulative_rules("hygiene")
```

```python
def test_missing_basis_stays_WARN_even_when_the_KIND_is_certified() -> None:
    # MOVED HERE FROM TASK 7, which could not state it: `_severity` and `_CERTIFIED_KINDS` are born
    # in THIS task, so the claim had nothing to constrain and the test could not have run.
    #
    # Kind certification and verdict-basis certification are INDEPENDENT facts. `hypothesis` being
    # in _CERTIFIED_KINDS says every root is pinned and renders; it says NOTHING about whether the
    # corpus carries verdict bases (>= 11 of 15 do not). Coupling them would let an uncertified rule
    # ride in on a certified one's coattails -- which is how a check that cannot pass ends up
    # failing 472 entities.
    from science_tool.validate.gates import cumulative_rules

    assert severity_for_kind("hypothesis") is Severity.ERROR
    assert "verdict.missing-basis" not in cumulative_rules("hygiene")
    assert "verdict.refutation-masked" in cumulative_rules("hygiene")   # the one that IS gated
```

- [ ] **Step 2: Implement — the shared interface**

```python
# science/src/science_tool/validate/kind_severity.py
"""Severity for KIND-level rules. One authority, consulted by every emitter that grades a kind.

A kind joins `_CERTIFIED_KINDS` at the END of its P2m slice -- never before. An uncertified
instrument may not fail anyone's build.

THIS SET CERTIFIES THE KIND, NOT EVERY RULE ABOUT IT. `hypothesis` here means: all 18 roots are
pinned, render, and validate. It does NOT mean the corpus carries verdict BASES -- >=11 of the 15
migrating verdicts do not, so `verdict.missing-basis` has its OWN ratchet, on its OWN axis, and
stays WARN. Two independent facts; do not let one certify the other. Rule-level ratchets do not
call this function.
"""

from science_model.validation import Severity

_CERTIFIED_KINDS: frozenset[str] = frozenset({"hypothesis"})


def severity_for_kind(kind: str) -> Severity:
    return Severity.ERROR if kind in _CERTIFIED_KINDS else Severity.WARN
```

- [ ] **Step 2b: Route ALL THREE kind-level emitters through it.** Two are in
  `validate/checks/hypotheses.py` — the `hypothesis.status-vocabulary` finding and the
  `hypothesis.dangling-lineage` finding (Task 7, which hard-coded `Severity.WARN`). **The third is in
  `validate/checks/supersession.py`** (Task 7a), which hard-codes `Severity.WARN` on
  `<kind>.unbacked-inverse` with a comment pointing at this step. All three take
  `severity_for_kind(...)` — and the third takes it **per finding**, `severity_for_kind(kind)`, not
  `severity_for_kind("hypothesis")`: it emits for every kind, and only the certified ones may ERROR.

  Then add **both** new rules to the `hygiene` tier in `validate/gates.py`:
  `hypothesis.dangling-lineage` **and `hypothesis.unbacked-inverse`** — kind-scoped names, because
  `gated_findings` keys on rule name alone (`gates.py:59-62`) and a generic name would gate every
  uncertified kind's WARNs along with them. A severity with no tier fails nobody's build; Task 7 and
  Task 7a each pinned their absence precisely so this task must invert both.

  **Omitting the third emitter is how the first two got stranded.** Task 7 wrote "ERROR is Task 12's
  ratchet" in a comment and Task 12 never touched it. This step is the only thing that closes that
  loop, and its own tests (Step 2c) fail if any of the three still hard-codes `WARN`.

- [ ] **Step 3: Re-assert the manifest, then validate.** Re-derive the roster and require **exact
  `(root, n)` set equality** against `/tmp/claude-1000/roster.json` (Task 11 Step 0). Totals are not
  a gate: `18/147` still holds if one root vanishes while another gains the same count. Only then
  run `science validate` across all 18 roots — **all exit 0** — plus our own suite for the three
  fixture roots. Flipping `hypothesis` to ERROR against a corpus that has drifted since
  certification is precisely the original incident.

  **Reuse Task 11 Step 3's loop verbatim** — `--project "$WT"`, the per-root import assertion, and
  a nonzero exit on any failure (Global constraint 0). This step decides whether a rule becomes
  **ERROR** for 147 files across 15 repositories. Certifying that against the **pinned public
  toolkit** — which has neither the mixin nor the checks — would arm the ratchet on the strength of
  a run that never looked at a single migrated file. *A gate certified by the wrong instrument is
  not a gate.*
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
- **A packet now has TWO spellings of a rival.** Task 6/8 declare the single-rival form
  (`rival_id`/`rival_name`/`rival_claim`/`discriminator_status`) because the corpus authors it and
  the model was silently dropping it — while `alternative_models: list[str]`, which the model
  declares and **nobody authors**, stays. That ends the data loss and leaves a design question:
  the right shape is probably `alternative_models: list[RivalModel]`, collapsing both. **Deleting a
  field on a model shared with other kinds is not a migration's business**, so the question is filed
  rather than answered here. The *drop* is fixed; the *duplication* is not.
- **The 169 residual status-vocabulary WARNs** on other kinds. They stay WARNs until their slices.

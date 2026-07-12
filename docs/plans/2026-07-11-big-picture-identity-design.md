# Big-picture identity and neighborhood — design

**Status:** proposed
**Date:** 2026-07-11
**Feedback:** 13 items — `fb-2026-07-11-002`…`-006`, `-010`…`-016`, `-023`
**Projects:** natural-systems, mm30, multiple-myeloma

---

## 1. The finding that reframes the cluster

Four of the thirteen are **already fixed**. They were fixed by the InstrumentResult
convergence (`bbedacbe`, merged in `fe2fb83b`), whose docstrings cite the feedback IDs by
number — and then nobody closed the tickets.

| Item | Claim | Reality |
|---|---|---|
| `-004` | `compute_topic_gaps` silently returns 0 rows | **Fixed.** Returns `unwired` / `empty` / `ok` with codes (`knowledge_gaps.py:233`) |
| `-014` | `count_research_orphans` can drift from `orphan_ids` | **Fixed.** `count_research_orphans` was *deleted*; only `list_research_orphans` remains (`validator.py:133`) |
| `-016` | `graph diff` never walks `entities/` | **Fixed.** `pp.entities_dir` is now first in `include_dirs` (`graph/io.py:367`) |
| `-023` | new entity files are never classified stale | **Fixed.** `walked`-set envelope + `new_file` status (`io.py:387`, `store/validation.py:348`) |

This is worth stating plainly because I nearly re-implemented all four. The lesson is not
"close your tickets" — it is that **a fix and the ticket that motivated it are two different
artifacts, and shipping one does not ship the other.**

And one of the four shipped without a guard:

> **`fb-016`'s fix has no regression test.** Delete `pp.entities_dir` from `include_dirs`
> today and the entire suite still passes. The original report even said so — *"No test in
> `tests/test_graph_io_revision_manifest.py` asserts anything about `entities/`"* — and the
> fix did not add one.

A fix with no guard is a fix with a half-life. That is the same defect class as the rest of
this cluster, so it is Task 1 rather than a footnote.

The remaining **nine** are four roots.

---

## 2. Root A — the graph does not distinguish a schema edge from a claim edge

**Items:** `fb-010` (gaps returns rows for other hypotheses), `fb-011` (gaps emits IRIs not CURIEs)

### 2.1 What is actually wrong

`graph/store/summary.py:788`:

```python
for subj, _, obj in knowledge:
    if not isinstance(subj, URIRef) or not isinstance(obj, URIRef):
        continue
    adjacency.setdefault(subj, set()).add(obj)
    adjacency.setdefault(obj, set()).add(subj)
```

**The predicate is discarded.** `_` is every relationship in the graph, collapsed. So
`hypothesis:0001 rdf:type sci:Hypothesis` becomes an undirected edge between the hypothesis
and the *class node*.

`sci:Hypothesis` is therefore a hub that **every hypothesis in the project is exactly one hop
from**. Which puts every hypothesis exactly **two hops from every other hypothesis**. The
default is `hops=2`.

Reproduced on a synthetic graph with three hypotheses and **zero edges between them**:

```
center = hypothesis:0001-alpha, hops=2 (default)  -> 3 rows  (alpha, beta, gamma)
center = hypothesis:0001-alpha, hops=1            -> 1 row   (alpha)
```

`hops=2` does not return a neighborhood. It returns *every entity of the same rdf:type*.

This is exactly what mm30 saw: 29 subagents each got the same six `evidential_fragility`
rows regardless of their center, and each independently worked out that the rows were
irrelevant and discarded them. **The instrument was wrong and the agents compensated.** A
global fragility list is indistinguishable from a neighborhood slice unless you already know
the graph — which is the one thing the caller was asking the instrument for.

### 2.2 The consequence nobody reported

Isolated nodes report **`degree=1`, not `degree=0`**. That 1 *is* the `rdf:type` edge.

So `structural_fragility(low_connectivity, degree=N)` has been counting schema edges as
connectivity for every node in every project. The fragility metric is inflated, uniformly,
and any threshold tuned against it was tuned against a wrong number. This was never in a
ticket — it fell out of reproducing fb-010.

### 2.3 The fix, and why it is one fix

Do not special-case `rdf:type`. Excluding one predicate leaves every *other* schema-level
predicate free to form a hub (any predicate whose object is a shared vocabulary term does
the same thing). The correct statement is:

> **Walk the entity graph, not the RDF graph.** An edge is admissible iff *both* endpoints
> are project entities.

`canonical_id_from_entity_uri()` (`store/identity.py:32`) already answers exactly that
question — it returns `None` for anything that is not a project-namespaced entity URI, which
includes `sci:Hypothesis`. It lives in the same package. `summary.py:30` already imports four
other names from `.identity` and simply does not import this one.

That single change resolves both items at once:

- **fb-010** — the class hub disappears, because a class node is not a project entity. The
  neighborhood becomes a neighborhood.
- **`degree`** becomes real entity degree. An isolated node reports `0`.
- **fb-011** — every node that survives the walk now *has* a CURIE by construction, so
  emitting `canonical_id_from_entity_uri(uri)` instead of `str(uri)` at `summary.py:848` is
  no longer a lookup that might fail. It is the identity we already computed to decide the
  node belonged in the walk at all.

fb-011 is not a formatting nicety. Its consequence was that subagents **could not cite the
gaps data at all** — the citation rule requires resolvable entity IDs and the validator flags
an IRI as `nonexistent_reference` — so they paraphrased the findings as ungrounded prose or
dropped them. The data was in the bundle and unusable at the point of use.

---

## 3. Root B — the synthesis output path is assumed rather than resolved

**Items:** `fb-002` (agent specs name a v2 path), `fb-013` (no rule for numbered filenames)

`commands/big-picture.md:141` says the target is `entities/synthesis/<hyp-id>.md`. Two
things are wrong with that.

**The agent specs disagree with the command.** `agents/hypothesis-synthesizer.md:24` and
`agents/emergent-threads-synthesizer.md:10,18` still name `doc/reports/synthesis/…` — the
**v2** path. At runtime the dispatcher's inlined path wins, so output currently lands in the
right place; the specs are stale rather than actively breaking. But an agent that follows its
own spec literally writes to a path nothing reads.

**`<hyp-id>.md` is not where synthesis lives in a numbered-entity project.** mm30 and
natural-systems both store synthesis as canonical numbered entities
(`0022-epigenetic-commitment.md`), bound to their hypothesis by a `hypothesis:` frontmatter
field. Following the command literally would create **29 new files alongside the 15 existing
ones** — duplicate synthesis entities for the same hypotheses, with the rollup pointing at one
set and the graph at the other. Both projects detected this by hand and built the
hypothesis→file map themselves before dispatching.

**The pattern already exists in this codebase.** `big_picture/digests.py:109` scans
`entities/synthesis/` for `report_kind: cluster-digest` and matches on frontmatter. It was
simply never applied to `hypothesis-synthesis`.

**Fix:** a resolver that scans `entities/synthesis/` for `report_kind: hypothesis-synthesis`,
maps each file by its `hypothesis:` frontmatter field, and returns the existing path —
falling back to `<hyp-id>.md` **only when no prior file exists**. The orchestrator passes the
*resolved* path to the agent instead of composing one. Partial coverage (mm30's prior run
covered 15 of 29) is a normal state the resolver must handle, not an error.

---

## 4. Root C — the canonical-ID contract is enforced only after the write

**Items:** `fb-012` (subagents truncate IDs), `fb-003` (no pre-write validation)

On the mm30 run, the first validate pass returned **84 issues, 76 from a single cause**:
subagents citing `interpretation:0192` where the canonical ID is
`interpretation:0192-t869-bcl2-dependency-venetoclax-hmcl-p3-supported`. The operator repaired
123 occurrences with a prefix-expansion script.

Three separate holes:

1. **The prohibition is in one spec, not both.** `hypothesis-synthesizer.md:64` now carries an
   emphatic never-truncate rule. `emergent-threads-synthesizer.md:60` says only "MUST be cited
   by its canonical ID" — no truncation rule. Half the fleet was never told.

2. **Prompt hardening demonstrably does not work.** natural-systems reported *4 of 14* agents
   truncating **despite** the emphatic prohibition. This is the load-bearing observation: we
   have already tried "tell them harder," and measured that it fails. Another round of stronger
   prose is not a fix, and this design does not propose one.

3. **The mapping is deterministic and we refuse to use it.** A unique `<kind>:<NNNN>` prefix
   expands to exactly one canonical ID. `validator.py:64` does a flat
   `if full_id not in known_ids` → `nonexistent_reference`, then stops. Both reporting projects
   independently wrote the same prefix-expansion script by hand.

**Fix, in two parts:**

- **Expand unambiguous prefixes** (`<kind>:<NNNN>` → canonical) deterministically, and **fail
  loudly on an ambiguous one** rather than guessing. The failure mode we are removing is a
  human running a repair script; the failure mode we must not introduce is a tool silently
  picking the wrong entity.
- **Validate staged output before reconciliation** (`science big-picture validate --staged
  <dir>`), so truncation is caught **before** canonical entities are overwritten, not after.
  Today validation is strictly post-hoc (`validator.py:1`: *"Post-hoc validator for generated
  big-picture synthesis files"*), so the repair is always done against already-published files.

---

## 5. Root D — three defects of measurement and order

### 5.1 `fb-015` — the word cap punishes the citation rule

The validator raises `thin_coverage_marker_mismatch` when `provenance_coverage` is `thin` and
the Arc section exceeds 150 words. `validator.py:75-77`:

```python
arc = _extract_section(text, "Arc")
word_count = len(arc.split())
if word_count > 150:
```

A naive whitespace split. Every
`pre-registration:0059-t869-bcl2-dependency-venetoclax-hmcl-powered-p3` counts as **one word**.

mm30's two violations (154 and 163 words) were caused by *citation density, not verbosity* —
trimming meant removing grounding rather than padding. And because `provenance_coverage` is
`thin` for all 29 mm30 hypotheses, **every** hypothesis is subject to the cap. The rule
systematically penalises the agents that cite most carefully.

**This interacts with Root C, and the interaction is the point.** Fixing fb-012 means agents
cite *full canonical IDs* — which are precisely the longest tokens in the document. **Fixing
fb-012 makes fb-015 strictly worse.** We would be tightening a rule that says "cite the long
form" while leaving in place a rule that charges you by the word for doing it.

They must ship together. `validator.py:29` already defines `REFERENCE_PATTERN`; strip entity
IDs before counting. The cap is meant to measure *prose verbosity*, and an entity ID is not
prose.

### 5.2 `fb-005` — retirement has no representation

`hypothesis:0009` in natural-systems was **rejected by a pre-registered confirmatory null**
(z = −0.889). It carries `status: retired`. But `phase` has no `retired` value —
`hypotheses_cli.py:30` is `click.Choice(["active", "candidate"])` — so it is still
`phase: candidate`.

Two consequences, both bad, and the second is worse than the ticket makes it sound:

1. The rollup's **"Candidate frames"** section selects on `phase == "candidate"`, so a **dead
   hypothesis is presented as a live candidate frame**.
2. Its 10 open questions still resolve against it, so the attention ranking puts the **retired
   hypothesis first by urgency** (`open_question_debt=10`, 27 incoming `bears_on`).

**The thing we disproved is the thing the system now tells us to work on most.** Retirement
currently has no defined effect on question re-homing or attention weighting — being *refuted*
makes a hypothesis *more* attention-worthy.

This is the one item with a `methodology:design` concern, and the only one needing a model
change: add `phase: retired`; exclude it from Arc / Research-fronts / Candidate-frames (or give
it a short **Retired** section); and have the validator flag questions still resolving to a
retired hypothesis as **re-homing debt** — which is the real work retirement creates.

Note `entities.py:206-211` deliberately keeps `retired` in `_LIVE_STATUSES` (visible). That is
correct and stays: retired means *refuted and visible*, not *hidden*. The bug is that visible
was silently equated with *live*.

### 5.3 `fb-006` — SHAs are stamped before the thing they attest is final

Documented order (`commands/big-picture.md:212-217`, then `:270`): sub-agents write → the
orchestrator stamps `git hash-object` of each per-hypothesis file into the rollup's
`synthesized_from` → **the validator runs**.

The validator legitimately rejects per-hypothesis files (that is its job — e.g. §5.1's Arc
cap). The documented repair is to re-dispatch the sub-agent, which **rewrites the file and
changes its SHA** — silently invalidating the rollup that already attested to the old one.
Nothing re-checks it. The staleness warning fires only on the *next* invocation, and is
explicitly *"informational — do not block execution."*

**Fix:** validate per-hypothesis files **before** the rollup stamps, or re-stamp after any
repair loop. A provenance record that is stamped before its subject is final is not provenance.

---

## 6. The through-line

Every one of the nine is the same shape as the two rulings already shipped:

- **InstrumentResult** (silent instrument): a check that could not run returned "clean."
- **Estimator doctrine**: a check that could not fail returned PASS.
- **Here**: an instrument that returned *the whole graph* was read as a neighborhood; an ID
  contract enforced only *after* the write was read as enforcement; a SHA stamped *before* the
  file was final was read as provenance.

In each case the artifact was **structurally incapable of carrying the meaning its consumer
assigned to it**, and nothing said so. The consumers — 29 subagents, twice — noticed and worked
around it by hand.

The unifying rule this cluster adds:

> **Identity and scope are properties the producer must establish, not properties the consumer
> should reconstruct.** If a row cannot be cited, the query should not have emitted it. If a
> path cannot be resolved, the orchestrator should not have composed it. If a prefix is
> unambiguous, the tool should expand it — and if it is ambiguous, the tool should say so
> rather than let an agent guess.

---

## 7. Non-goals

- **No new prose telling agents to try harder.** natural-systems ran 4-of-14 truncations
  *against* an emphatic prohibition. Prompt hardening has been measured and it failed. Where
  this design touches agent specs, it is to *correct a factual error* (the v2 path) or to close
  the asymmetry between the two specs — not to raise the volume.
- **No change to `_LIVE_STATUSES`.** `retired` stays visible.
- **No general semantic gap model.** `compute_topic_gaps` remains the legacy topic-coverage
  surface; this cluster does not redesign it.
- **No re-litigation of the four already-fixed items** beyond adding the missing guard and
  closing them.

---

## 8. Acceptance

1. `graph gaps <center> --hops 2` on a graph whose hypotheses share only `rdf:type` returns
   **the center alone** — the regression test is the three-hypothesis/zero-edges graph from
   §2.1, which returns 3 rows today and must return 1.
2. An isolated entity reports `degree=0`, not `degree=1`.
3. `graph gaps` rows carry CURIEs; a row emitted by gaps can be pasted into a synthesis file
   and pass `big-picture validate`.
4. A hypothesis with an existing numbered synthesis entity resolves to **that file**; a
   hypothesis with none falls back to `<hyp-id>.md`. Partial coverage is handled.
5. A unique `<kind>:<NNNN>` prefix expands to its canonical ID; an **ambiguous** prefix fails
   loudly.
6. Staged output can be validated before reconciliation.
7. A `retired` hypothesis does not appear under Candidate frames and does not lead the
   attention ranking; its unre-homed questions surface as re-homing debt.
8. The Arc word cap does not count entity IDs.
9. `entities/` in the manifest walk-set is **guarded by a test** that fails if it is removed.
10. All 13 feedback items are `addressed` (the terminal status; there is no `resolved`).

---

## 9. Sequencing

Task 1 is the guard for the already-shipped fix, because it is the cheapest and it is
currently unprotected. Roots A and D-1 carry the correctness weight.

| # | Work | Items | Note |
|---|---|---|---|
| 1 | Guard `entities/` in the walk-set; close the 4 stale tickets | `-004 -014 -016 -023` | fix already shipped; guard did not |
| 2 | Entity-graph adjacency + CURIE emission | `-010 -011` | one fix, two items; also corrects `degree` |
| 3 | Arc word cap excludes entity IDs | `-015` | **must precede or ship with Task 4** |
| 4 | Prefix expansion + `--staged` validation + spec symmetry | `-003 -012` | worsens `-015` if shipped alone |
| 5 | Synthesis path resolver + correct the stale v2 agent specs | `-002 -013` | pattern exists at `digests.py:109` |
| 6 | `phase: retired` + attention/candidate exclusion + re-homing debt | `-005` | model change; only `methodology:design` item |
| 7 | Validate-before-stamp (or re-stamp after repair) | `-006` | provenance ordering |

**Task 3 before Task 4 is not cosmetic.** Shipping the ID-discipline fix while the word cap
still charges by the word for long IDs would tighten a rule and simultaneously penalise
compliance with it.

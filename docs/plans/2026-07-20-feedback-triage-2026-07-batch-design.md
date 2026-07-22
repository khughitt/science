---
title: Feedback Triage — 2026-07 batch (106 open items) — Design
status: proposed
created: '2026-07-20'
updated: '2026-07-22'
revision: v10 (step 13 Batches H/I/G/J-rest — on-request-only dataset availability (analysis-ineligible) + no-required-capabilities coverage class + catalog authorization gate; provenance-aware missing_source_refs + tolerant decision-digest parser; pre-registration & design-integrity guidance (frozen-vehicle regen, output provenance, full-resolution count ledger, blind-erosion, before/after discipline, training-side confound gate, technical cross-tab). G-024 deferred. [v9: step 12 Batch D; v8: step 11 Batch C])
---

# Feedback Triage — 2026-07 batch

## Scope

Triage of the **106 open `science feedback` entries** spanning 2026-07-07 →
2026-07-19. This document batches them into work units, ranks by severity,
records the blocking design decisions, and proposes a sequence.

Implementation status is tracked inline per batch. As of v3 the only code shipped
is the Tier-0 inquiry-export URI fix (branch `fix/inquiry-export-uri`, see
Finding 1); everything else is unstarted.

Composition: 72 `tooling` / 34 `methodology:*`; 58 `gap`, 29 `friction`,
8 `guidance`, 8 `suggestion`, 3 `positive`. Eight projects reporting, dominated
by post-acute-infection (44), science (15), natural-systems (11),
multiple-myeloma (10).

Every one of the 106 is assigned to exactly one batch. The assignment is
enumerated in the **Batch manifest** below and was verified bijective by script
(no duplicates, no omissions, no unknown ids) rather than asserted — an earlier
revision of this document claimed completeness without checking and was wrong on
five counts.

## Batch manifest

Authoritative ID → batch assignment. Counts are derived from this table; the
narrative batch sections below describe it but do not define it.

| Batch | N | Items (`fb-2026` prefix elided) |
|---|---|---|
| **A** — Commons federation & overlay policy | 12 | `-07-09-001`, `-07-11-001`, `-07-11-018`, `-07-11-019`, `-07-11-020`, `-07-11-021`, `-07-12-006`, `-07-12-007`, `-07-16-004`, `-07-16-005`, `-07-18-005`, `-07-19-005` |
| **B** — Instruments that cannot fail | 8 | `-07-11-017`, `-07-12-002`, `-07-12-003`, `-07-12-009`, `-07-18-003`, `-07-18-004`, `-07-19-001`, `-07-19-003` |
| **C** — Inquiry subsystem | 6 | `-07-11-030`, `-07-11-031`, `-07-11-032`, `-07-19-002`, `-07-19-006`, `-07-19-007` |
| **D** — Status vocabulary | 4 | `-07-11-034`, `-07-12-004`, `-07-12-005`, `-07-12-008` |
| **E** — explore-ideas | 7 | `-07-11-022`, `-07-17-002`, `-07-17-003`, `-07-17-004`, `-07-17-005`, `-07-17-009`, `-07-17-011` |
| **F** — Transient-artifact layer | 5 | `-07-10-020`, `-07-10-021`, `-07-10-022`, `-07-16-006`, `-07-17-001` |
| **G** — curate mechanics | 5 | `-07-10-017`, `-07-10-018`, `-07-10-019`, `-07-10-023`, `-07-10-024` |
| **H** — Author-request data | 3 | `-07-07-003`, `-07-17-008`, `-07-17-010` |
| **I** — catalog-datasets | 2 | `-07-17-006`, `-07-17-007` |
| **J** — Pre-registration & design integrity | 8 | `-07-11-024`, `-07-11-025`, `-07-11-026`, `-07-11-027`, `-07-11-028`, `-07-11-033`, `-07-18-007`, `-07-18-008` |
| **K** — Estimand discipline | 11 | `-07-18-009`, `-07-18-010`, `-07-18-012`, `-07-18-013`, `-07-19-008`, `-07-19-009`, `-07-19-010`, `-07-19-011`, `-07-19-012`, `-07-19-013`, `-07-19-014` |
| **L** — Statistics / estimator certification | 9 | `-07-12-010`, `-07-12-011`, `-07-12-012`, `-07-12-013`, `-07-12-014`, `-07-12-015`, `-07-13-001`, `-07-13-002`, `-07-13-003` |
| **M** — Feedback & post-mortem system | 3 | `-07-11-029`, `-07-16-001`, `-07-18-011` |
| **N** — Singletons & small fixes | 23 | `-07-07-001`, `-07-07-002`, `-07-08-001`, `-07-08-002`, `-07-08-003`, `-07-10-001`, `-07-10-002`, `-07-10-003`, `-07-10-004`, `-07-10-005`, `-07-10-025`, `-07-10-026`, `-07-11-007`, `-07-11-008`, `-07-11-009`, `-07-12-001`, `-07-16-002`, `-07-16-003`, `-07-18-001`, `-07-18-002`, `-07-18-006`, `-07-19-004`, `-07-19-015` |
| **Total** | **106** | |

Assignment notes for the non-obvious placements:

- `-07-11-017` → **B** (not N). The entry covers both the evidence-line template
  gap *and* the top-level `supersedes:` silent no-op; the latter is the
  load-bearing half and is what the Batch B lint addresses.
- `-07-16-001` (`feedback show`) → **M** (not N). It is cheap enough for the
  ship-today tier but belongs with the feedback-system work it enables.
- `-07-18-008` → **J** (not L). It is the design-time cross-tab habit that pairs
  with `-07-18-007`'s training-side gate; both are pre-freeze design integrity.
- `-07-07-002` and `-07-08-001` → **N**, together. Both are
  `command:review-pipeline` rubric-fit reports (the 9-dimension rubric is
  graph-inquiry-shaped and maps awkwardly onto a prose `kind:plan` or an
  already-completed simulation). They should be worked as one small design call.

---

## Finding 0 — the backlog is lying about recurrence

**`recurrence` is `1` on all 106 entries. Deduplication has never fired.**

`find_duplicate` (`feedback.py:206`) requires an exact `target` string match, an
exact `concern` match, and bidirectional substring containment on the summary.
But `--target` is **free text by design** (`commands/post-mortem.md:35` says so
explicitly), and the corpus carries **57 distinct targets for 106 entries** —
including six spellings of the commons surface:

    command:commons · command:commons-promote · command:commons-promote-dataset
    cli:science commons promote · cli:commons · commons:overlay

and near-miss pairs `command:critique-approach` / `commands:critique-approach`,
`validate:status_vocabulary` / `validate:check_status_vocabulary`,
`command:validate` / `science:validate`.

Two provable misses in this batch alone:

- **"available on request is dead data"** filed three times — `fb-2026-07-17-010`
  (`command:catalog-datasets`), `fb-2026-07-07-003` (`command:dataset`), and in
  part `fb-2026-07-17-008`.
- **"explore-ideas --apply produces hollow entities"** filed twice —
  `fb-2026-07-11-022` (`command:explore-ideas`) and `fb-2026-07-17-011`
  (`cli:explore-ideas`).

Each pair differs *only* in target spelling. The tool's own claim in
`commands/post-mortem.md:56` — "The tool detects recurrence automatically" — is
currently false, and the failure silently inflates the backlog while hiding the
recurrence signal that is supposed to drive prioritisation.

This gates the value of every future triage, so it is sequenced immediately after
Tier 0.

### But do not simply loosen the matcher

Broadening the match is **not** sufficient, and on its own is actively harmful.
The current merge path is destructive:

```python
dup = find_duplicate(fb_dir, target=target, summary=summary, concern=concern)
if dup is not None:
    dup.recurrence += 1
    save_entry(fb_dir, dup)
    ...
    return                      # feedback_cli.py:83-88
```

It increments an integer and returns. The new filing's `project`, `category`,
`detail`, and `related` are **discarded entirely**. Today that loss is invisible
because the matcher never fires; loosening the matcher would convert a dormant
bug into routine, silent evidence destruction — losing exactly the
cross-project recurrence evidence the change is meant to surface. Note the
existing consequence too: an entry at `recurrence: 5` still reports **one**
project, so `group_for_triage`'s `projects` list undercounts reach.

**Required design, in order:**

1. **Make recurrence non-lossy first.** An entry gains an `occurrences: []` list —
   one record per filing, carrying at minimum `{date, project, category, detail}`.
   `recurrence` becomes `len(occurrences)` (derived, not stored), so no filing is
   ever discarded and per-occurrence project/detail survive for triage.
2. **Only then normalise target matching** — fold `command:`/`commands:`/`cli:`/
   `science:` prefix variance and collapse whitespace. This is a safe *exact-match
   widening*: it merges spellings that genuinely denote one surface.
3. **Keep fuzzy matching advisory, never automatic.** Anything beyond
   normalised-exact (summary similarity, dropped `concern` equality) should
   **suggest** — print candidate ids and exit, or require `--merge-into <id>` —
   rather than merge. An automatic destructive merge on a fuzzy match is strictly
   worse than a duplicate entry, because a duplicate is recoverable and a
   discarded filing is not.
4. **Add `science feedback targets`** to list existing targets, so a filer picks
   an existing spelling instead of minting the 58th. Prevention beats
   reconciliation given `--target` is free text by design.

Steps 1–2 are the actual fix for Finding 0. Steps 3–4 are what keep it from
becoming a new silent-data-loss defect — which would be a poor outcome for a
document whose Tier 0 is entirely silent data loss.

---

## Finding 1 — `fb-2026-07-19-001` is real, open on main, and its "already fixed" verdict is wrong

`docs/plans/2026-07-18-causal-tooling-gaps.md` records the causal `export-pgmpy`
named-graph mismatch as **"already fixed"**, attributing the post-acute report to
an older pinned toolkit, and cites
`tests/test_causal.py::TestExportPgmpy::test_export_pgmpy_reads_compiled_patch_inquiry_edges`
as evidence. **Both the verdict and the evidence are wrong.** Verified
empirically against current `main` on 2026-07-20.

### The defect

Writer and reader disagree on the inquiry URI:

| | Construction | `patch-definition:compound-boundary-conditions-interaction-dag` → |
|---|---|---|
| **Writer** — `graph/inquiry_compile.py::inquiry_uri` | `PROJECT_NS["inquiry/" + canonical_id.split(":")[-1]]`, hyphens **preserved** | `inquiry/compound-boundary-conditions-interaction-dag` |
| **Reader** — `causal/export_pgmpy.py:103` | `_slug(slug)` = `re.sub(r"[^a-z0-9]+", "_", …)`, hyphens → **underscores** | `inquiry/compound_boundary_conditions_interaction_dag` |

The reader resolves an empty graph, so `members` is empty, so the member filter
at `export_pgmpy.py:154` (`if s not in members or o not in members: continue`)
drops **every** edge — including the ones the `graph/causal` union at line 149
was added to rescue. The union fix is real but is gated behind the empty member
set, which is why verifying the union did not settle the question.

Measured on a fixture that reproduces the production URI convention
(`normalize_slug=False`):

    MODEL EDGE LIST for normalize_slug=True  : '("x", "y"),'
    MODEL EDGE LIST for normalize_slug=False : ''          # DiscreteBayesianNetwork([])

`_get_causal_edges_for_inquiry` returns **0 edges** for a hyphenated slug. This
is exactly the reported symptom.

### Why the regression test certified a phantom

Two independent reasons, and both matter:

1. **The fixture writes the reader's convention, not the writer's.**
   `tests/conftest.py::build_inquiry_graph` takes `normalize_slug`, and
   `test_causal.py::_build_compiled_inquiry_graph` hardcodes `normalize_slug=True`.
   Its own docstring is explicit: *"the causal tests use hyphenated slugs and rely
   on the retired `add_inquiry` mutator's `_slug` normalization so the readers
   resolve the same inquiry URI."* Production compilation does not normalise, so
   no test exercises the real URI.

2. **The assertion cannot fail.** The test asserts `'("x", "y")' in script`. The
   generated script always ends with
   `ci.get_all_backdoor_adjustment_sets("x", "y")` whenever treatment is `x` and
   outcome is `y` — so the assertion is satisfied by the adjustment-set call line
   **even when the model is `DiscreteBayesianNetwork([])`**. Confirmed: the
   `normalize_slug=False` case above passes this assertion while emitting an empty
   model.

This is the defect class the backlog is already full of — a test that asserts an
artifact's own wording and thereby certifies the phantom (cf. `fb-2026-07-11-021`,
whose generalisation was *"any `x-` annotation naming a template artifact should be
guarded by a test that reads the template, not the schema"*). Here the same
mistake occurred **in the fix for another instance of it**.

### Required actions

- Correct `docs/plans/2026-07-18-causal-tooling-gaps.md` — the "Not a current bug
  (verified 2026-07-18)" section is wrong; keep the union finding, retract the
  verdict.
- Make writer and reader share **one** URI constructor (prefer the writer's
  hyphen-preserving form; `store/inquiry.py` already *discovers* `sci:Inquiry`
  rather than reconstructing, which is the robust pattern).
- Assert on the **parsed model edge list**, not on a substring of the whole
  script. Reuse the `normalize_slug` parameter to test both conventions.
- ~~Reconcile authored against resolved counts in the exporter.~~ **Dropped after
  implementation — see below.** A causal inquiry with no `flow_edges` is
  *currently valid* (`flow_edges` defaults to empty and `_estimand_rules` requires
  only `treatment`/`outcome` for `profile="causal"`,
  `model/src/science_model/patch_definition.py:98-118`), so a naive "fail on zero
  edges" would reject conforming inquiries. But the reconciliation table this
  document originally specified turned out to be unnecessary: routing the reader
  through the discovery resolver removes the mechanism that produced a
  zero-resolved-from-nonzero-authored state in the first place. Building it anyway
  would be guarding a case that can no longer arise.

### Status: FIXED (2026-07-20, branch `fix/inquiry-export-uri`)

`_get_causal_edges_for_inquiry` no longer reconstructs the URI. The resolution
logic already inside `get_inquiry` — discovery via `_discover_inquiries`, prefix
stripping, and normalization-drift tolerance — was extracted as
`store/inquiry.py::resolve_inquiry` and is now the single path used by both
`get_inquiry` and the exporter. The vacuous assertion was replaced with a
`_model_edges()` helper that parses the `DiscreteBayesianNetwork([...])` edge
list, and a `_build_production_inquiry_graph` fixture (no slug normalization)
now exercises the real writer convention.

Verified: new test red before / green after; full suite **9475 passed, 7
skipped**; ruff and pyright unchanged from the `main` baseline (4 and 7
pre-existing errors respectively, all in untouched files).

### Correction: `fb-2026-07-19-003` does not reproduce

The reported escalation — *"a reader who runs `uv add pgmpy` then gets GREEN
identifiability checks computed over an empty graph — worse than a skip"* — was
tested directly with `pgmpy` installed and **does not occur**:

    identifiability  status=skip  msg='No causal edges found — cannot assess identifiability'
    adjustment_sets  status=skip  msg='No causal edges found'

`validate_inquiry_dataset` resolves via `_discover_inquiries` — a *different*
path from the exporter's reconstructed URI — and already carries an explicit
`unwired` guard whose docstring states the doctrine verbatim ("An empty subgraph
is not evidence of validity; it is evidence that the check could not run"). The
reporter reasoned plausibly from a true premise (the exporter emitted an empty
model) to a false conclusion about the validator, because the two use different
resolvers.

That behaviour had **no test coverage**, so a regression guard was added
asserting the invariant that identifiability/adjustment_sets never report `pass`
over an edgeless model — holding in both pgmpy configurations. The guard was
mutation-tested: flipping the skip to a `pass` makes it fail.

**Residual of `-19-003`:** only a `command:critique-approach` documentation fix
(Step 2 should assert a non-empty model before reasoning over it). Not a toolkit
change, and no longer Tier 0.

---

## Tier 0 — silent corruption. Ship before anything else.

These share one shape: **the tool reports success while destroying or fabricating
state.** Nothing else in the backlog is in this class.

| ID | Defect |
|---|---|
| `fb-2026-07-16-004` (addendum) | `commons promote` conflict prompt `[k]` silently discards canonical body sections — **measured 347 lines across 3 real papers**. Loss runs *backwards from quality*: the thinner project that promoted first wins. Following the tool's own sanctioned remediation destroys the better document. |
| `fb-2026-07-16-005` | Paper overlays are **inert** whenever `references.bib` owns the id (7/21 in cancer/meta). Pins never validated, `related:` edges never materialise, `validate` reports green. Converting to overlays clears 22 errors *while dropping the content the overlay exists to carry*. Confirmed on a second project with a byte-identical control. |
| `fb-2026-07-11-018` | `commons promote` mints colliding canonical citekeys with no cross-project check. Liu2025/Qiao2025 broke `graph build` in untouched projects. Author+year collisions recur by construction. |
| `fb-2026-07-16-004` (main) | Promotion retroactively makes bystander projects' local owners ambiguous → **22 edges silently dropped from a graph that reports itself fresh**. |
| `fb-2026-07-19-001` | See Finding 1. An identifiability check that cannot fail. **FIXED 2026-07-20** on `fix/inquiry-export-uri`. (`-003` was triaged here too but does not reproduce — see the correction in Finding 1; it demotes to a `critique-approach` doc fix in Batch B.) |
| `fb-2026-07-11-024` | Pre-registration froze a **gitignored** build artifact as its vehicle. The pipeline regenerated it, destroying the registered export irrecoverably and exposing observed values → a downstream cohort decision became post-observation. Preventable with `git check-ignore` at commit time. |

**Sequencing constraint:** `fb-2026-07-16-005(d)` warns that fixing the overlay
bug makes pins enforceable *for the first time*, turning cancer/meta red (it pins
1.0.0 against canonicals now at 1.1.0). Land the pin refresh in the same change.

> **Retracted 2026-07-20 — the anticipated breakage does not reproduce; no pin
> refresh was needed.** Audited all **292** pinned overlays across the sibling
> repos (cancer/*, health/*, meta) against the current `~/d/science-commons`
> canonicals: **0 mismatches** — 285 pin `1.0.0` against canonical `1.0.0`, and
> the 7 canonicals that *did* advance to `1.1.0` already carry refreshed `1.1.0`
> pins (the bump and the overlay refresh landed in lockstep, exactly as intended).
> Ground-truthed with the current local-main toolkit (which runs the fixed
> overlay-closing code, so bib-owned-id overlays are now actually validated):
> `science validate` on health/meta, cancer/mechanisms/evolution, and
> health/comparisons/pan-disease surfaced **zero** pin-version errors. The pin
> instrument is not vacuous — `test_graph_commons_sources.py` writes a `9.9.9`
> overlay against a `1.0.0` canonical and asserts `OverlayValidationError`, so a
> genuinely stale pin *would* fail; the corpus is green because the pins are
> genuinely current. This is the `fb-2026-07-19-003` pattern: a plausible report
> whose premise no longer holds against the live state. **The one real error the
> sweep surfaced is unrelated to pins:** commons canonical `papers/Cheek2025.md`
> carries a `dataset_usage` ref to `dataset:uk-biobank`, which has no commons
> canonical — a dangling reference *in the shared store* that fails
> cancer/mechanisms/evolution's graph audit. Tracked separately; it is a commons
> data-integrity defect, not a pin-refresh obligation.

---

## Batches

### A. Commons federation & overlay-schema policy — 12 items
`fb-2026-07-16-004`, `-16-005`, `-11-018`, `-11-019`, `-11-020`, `-11-021`,
`-11-001`, `-09-001`, `-19-005`, `-18-005`, `-12-006`, `-12-007`

Largest cluster, and the one with a genuine blocking decision.

Three items — `-11-001` (`paper_kind`), `-18-005` (`tier`), `-09-001`
(`provided_capabilities`) — all *surface* as `additionalProperties:false`
rejecting a field. They share a symptom but **not** a resolution: each asks a
different question about who owns the field. A single open-vs-closed ruling
cannot settle them, and treating them as one bug would ship the wrong answer for
at least two.

| Field | Report | Real question | Semantics | Likely resolution |
|---|---|---|---|---|
| `paper_kind` | `-11-001` | Is this project bookkeeping or canonical metadata? | **Project-only.** Set by `research-papers`/`review-books`; meaningless commons-side. | Strip or allowlist at overlay-build time; never promoted. |
| `tier` | `-18-005` | May a project disagree with the canonical value? | **Canonical with project override.** Both values are legitimate and must coexist. | Add optional `tier`/`tier_rationale` to the overlay; define override precedence. |
| `provided_capabilities` | `-09-001` | Is capability intrinsic to the dataset or project-local? | **Canonical.** The report argues capability is intrinsic; promotion currently *strips* it. | Preserve on the canonical at promote; overlay carries nothing. |

So the deliverable is not an openness ruling but a **per-field ownership and
merge-policy table** — `project-only` / `canonical` / `canonical-with-override` —
with the overlay schema and the promote-time builder both derived from it. That
table is the thing to design; the three reports are its first three rows, and
`-11-021` and `-11-020` (canonicalization lossiness) constrain it further.
**Resolved by D1 (2026-07-21) — see [Blocking design decisions](#d1--per-field-ownership-and-merge-policy--resolved-2026-07-21).**
The grounding pass established that the table already exists as `science:merge`
schema annotations, so the ruling adds one policy value (`override`, for `tier`)
and reclassifies these three fields; the "Likely resolution" column above is the
confirmed resolution.

Separately, the commons id namespace is global with zero cross-project awareness
(`-11-018`, `-16-004`, `-11-019`); one federation-awareness pass at promote time
closes all three.

`-11-021` is already fixed (`29ffdea4`) — close it, but keep its generalisation as
a lint (see Finding 1, which is a fresh instance).

### B. Instruments that cannot fail — 8 items
`fb-2026-07-12-002`, `-12-003`, `-12-009`, `-18-003`, `-18-004`, `-11-017`,
`-19-001`, `-19-003`

Direct continuation of the estimator-doctrine / instrument-result-convergence
work. `validate/checks/prereg.py` gates on `^type:` while every template emits
`kind:` → dead code. The pre-registration freeze point is inert (an uncommitted
pre-reg produces byte-identical edges to a committed one). `numeric-anchor` reads
singular `artifact` while the schema defines plural `artifacts`, so correct
entities *lose* the exemption and stale invented paths *keep* it.

**Proposed high-leverage addition:** a generic lint for *"declared frontmatter key
that materialises zero triples"*. It would have caught `-12-003`, `-11-017`, and
the known `phase` defect in one rule.

> **Step 5 SHIPPED 2026-07-21, branch `batch-b-remainder`.** The grounding pass
> falsified most of this batch's premises — most items were already fixed, and the
> "generic lint" already exists in its *correct* form and its general form was
> deliberately rejected:
>
> - **The generic lint is NOT to be built.** `check_non_materializing_fields`
>   (`validate/checks/materialization.py`, merged 2026-07-15) already implements it
>   in the only sound form — a small kind-aware denylist of keys that name a graph
>   relation predicate AND have a `relations:` equivalent (`supersedes`, `amends`).
>   Its own design doc (`docs/plans/2026-07-15-non-materializing-fields-design.md`
>   §8) **explicitly rejected** the fully-general "any declared key → zero triples"
>   rule as speculative (YAGNI). It is not merely unbuilt — it is *wrong*: under
>   `extra="allow"` (D3.3) most frontmatter keys legitimately materialise no triples
>   (ad-hoc-read display fields), so a general rule would cry wolf on exactly the
>   `phase` field the proposal named — `phase` is an *intended* decoration, not a
>   defect. The preserve-and-surface story is already covered by `extra="allow"` +
>   the graph-audit `undeclared_key` diagnostic (reference-named keys on non-strict
>   kinds). This closes `-12-003` (its `extra="ignore"` premise is stale) and
>   `-11-017` pt3 (already caught).
> - **`-12-002` prereg dead code** — already fixed 2026-07-20 (gates on `kind`, not
>   `^type:`; the two WARNs are live).
> - **`-18-004`** (singular `artifact`) — already fixed; `entity_source_candidates`
>   reads both `artifact` and `artifacts`. **`-18-003`** (coarse/unverified) — the
>   two asks are already in: an existence check (`index.resolve`) and a
>   paragraph-scoped candidate layer; the residual entity-level exemption is now
>   resolution-gated (invented/stale paths no longer pass), which is acceptable.
> - **`-12-009`** (inert freeze point) — **the one real code fix.** Owner ruling:
>   gate the pre-registration commitment/`bearsOn` edges on the freeze status set
>   `{committed, amended}` (`materialize.py::_FROZEN_PRE_REGISTRATION_STATUSES`);
>   an `active`/draft pre-reg now derives no edges, so committing is load-bearing.
>   Fleet-certified before shipping: of 141 pre-regs, 123 are `committed` (keep
>   edges) and 18 un-frozen (`active`/`complete`/`draft`/`proposed`, across NS/mm30/
>   cycles) lose derived `bearsOn` — the intended correction; `bearsOn` is derived
>   so nothing dangles and no `validate` turns red, and consumers pick it up on pin
>   bump.
> - **`-11-017` pt1** — documented `dataset_usage` (with the DEPENDENCE-role
>   distinction: `analyzed | set_definition_source | training | upstream` count;
>   `cited | validation_source | reference` do not) and `run_refs` (Path B) in
>   `templates/evidence-line.md` (+ packaged shadow). pt2 (interp `relations:` form)
>   was already in the canonical template.
>
> Closes B[`-12-002`, `-12-003`, `-12-009`, `-18-003`, `-18-004`, `-11-017`]
> (`-19-001`/`-19-003` closed in step 1). No new lint shipped — by design.

### C. Inquiry subsystem — 6 items
`fb-2026-07-19-006`, `-19-007`, `-11-030`, `-11-031`, `-11-032`, `-19-002`

Coherent and currently incoherent. Two entity kinds (`inquiry` vs
`patch-definition`) where `validate` discovers the former and only the latter can
produce a subgraph → MM30's 23 inquiries emit `no_inquiry_subgraph` forever (74%
of its validation warnings). The offered bridge, `inquiry import`, **crashes on
every one** (status `Literal` mismatch, raw traceback) and is chicken-and-egg
anyway: it reads structure from the subgraph it is meant to bootstrap. There is
no user-guide documentation for inquiries at all. **Needs a design pass, not
patches.**

> **Step 11 SHIPPED 2026-07-22, merged `--no-ff` local main `4525887a`
> (branch `batch-c-inquiry`), NOT pushed.** All 6 entries closed. Grounding
> confirmed every claim was live (the two-kind gap is exactly as reported:
> thin `InquiryEntity` kind:inquiry vs. structured `PatchDefinitionEntity`
> patch_type:inquiry — only the latter compiles a subgraph). Four owner design
> forks answered via AskUserQuestion (all recommendation-first):
>
> - **`-11-030` — validate splits the no-subgraph case.** `validate_inquiry_dataset`
>   now distinguishes a thin doc-authored inquiry with no patch-definition backing
>   (`no_inquiry_block`, surfaced **INFO** in `graph.py` — expected, not a defect)
>   from a patch-definition inquiry whose subgraph is genuinely missing
>   (`no_inquiry_subgraph`, stays **WARN**). Discriminator: presence of a
>   `patch-definition:<slug>` entity in the dataset. Ends MM30's 23 forever-WARNs.
>   The unwired doctrine is preserved (structural checks still never pass over an
>   empty graph).
> - **`-11-031` / `-11-032` — `inquiry import` fails cleanly.** `get_inquiry` now
>   reports `has_compiled_subgraph`; import refuses a thin doc-authored inquiry up
>   front with actionable guidance, and wraps both the not-found `ValueError` and
>   the final model build in `click.ClickException` (no raw pydantic tracebacks).
>   The chicken-and-egg bridge no longer emits an empty profile.
> - **`-19-007` — `estimand_type` on `InquiryProfile`** (`interventional` default |
>   `descriptive` | `associational`). A non-interventional causal estimand no longer
>   needs a fake treatment placeholder (treatment/outcome optional), and
>   `export_pgmpy_script` omits `get_all_backdoor_adjustment_sets` for it — the
>   silent-wrong-output (adjustment sets for an interventionist effect the author
>   rejected) is prevented at its source. Wired emit → `get_inquiry` → exporter.
> - **`-19-002` — critique reports write to `entities/interpretations/`** (a critique
>   is an interpretation), never `entities/inquiries/` (which collides with numbered
>   `kind:inquiry` entities).
> - **`-19-006` — critique-approach documents the `science dag` port path** for
>   two-axis `edge_status`/`identification` labels (consumed by the `science dag`
>   subsystem, not inquiry `FlowEdge` which is `extra="forbid"`). No FlowEdge model
>   change — declined adding fields only a separate subsystem reads.
>
> Full suite (9625 passed) + model + snapshot + real_projects all exit 0;
> ruff/pyright at the pre-existing baseline (4 ruff in untouched
> `test_numeric_binding.py`; 7 pyright in untouched files). Codex mirror
> regenerated for critique-approach. **Batch C fully closed.**

### D. Status vocabulary — 4 items
`fb-2026-07-11-034`, `-12-004`, `-12-005`, `-12-008`

⚠️ **Check the `status-vocab-certification` branch before implementing** — Phase 1
shipped there unmerged, and `-11-034` is its fallout (MM30: *passed, 31 warnings*
→ **184 errors** with zero MM30 change).

`-11-034`'s second observation deserves promotion: the graded WARN-pre-v3 /
ERROR-on-v3 rollout is **inverted**, because the most-migrated project has the
largest legacy corpus — v3 status is an inverse proxy for "safe to hard-fail".
`-12-004` / `-12-005` are commands prescribing statuses illegal in every
vocabulary (trivial). `-12-008`: `ProjectEntity.readiness()` is "ready iff status
== done", but `done` is in no kind's vocabulary, so a task blocked by a
plan/method/pre-registration/workflow/search can **never** become ready.

> **Step 12 SHIPPED 2026-07-22, merged `--no-ff` local main `5ce079ec`
> (branch `batch-d-status`), NOT pushed.** All 4 entries closed. **Grounding
> overturned the batch's premise: the `status-vocab-certification` branch is NOT
> half-done — its work merged to main via the D5 authoritative-entity-schema merge
> `537f52c1`** (`86ca2264 fix(validate): certify the status vocabularies before
> enforcing them`, `2c84898a refactor(kinds): derive ... status-vocab maps from
> CORE_PROFILE`). The old Phase-1 commit `e462b5f7` is NOT in main; a more complete
> version superseded it.
>
> - **`-11-034` — already addressed by the merged D4/D5, closed with note.** The
>   check is now `severity_for_kind(kind)` with `_CERTIFIED_KINDS = {"hypothesis"}`,
>   so every non-hypothesis status finding is **WARN** — MM30's 184 "errors" are WARN,
>   the build no longer fails. The `layout_version >= 3` axis (which -11-034's second
>   observation called inverted) is **deleted**. Per-kind vocabularies were widened
>   (plan has `draft`; pre-registration has `committed`/`amended`; question has
>   `answered`/`partially-answered`/`deferred`). Residual project-side synonym drift
>   is greenlight-gated project migration, out of toolkit scope.
> - **`-12-008` — the one real code fix.** `ProjectEntity.readiness()` now returns
>   ready for any successfully-concluded status:
>   `READY_STATUSES = {done, complete, answered, committed, amended}` (ClassVar).
>   Owner ruling: the concluded-success set (not the minimal `+complete`, not per-kind
>   overrides). Abandoned-terminal states (retired/superseded/archived/deprecated) stay
>   NOT ready — an abandoned blocker does not satisfy its dependents. `done` kept for the
>   task open-set convention.
> - **`-12-004` / `-12-005` — command-doc fixes.** `plan-analysis.md` prescribed
>   `status: ready|ready-with-caveats|not-ready` (none in the plan vocabulary; nothing
>   read it — `plan_gate` computes readiness from inputs) → now `status: draft`, with the
>   ready/not-ready verdict documented as belonging in the existing **Readiness Decision**
>   body section. `critique-approach.md` instructed `Update the inquiry status to
>   critiqued` (not in the inquiry vocabulary; review-state is not lifecycle) → removed;
>   the critique interpretation entity is the record of review, inquiry status unchanged.
>
> Full suite (9627 passed) + model + snapshot + real_projects all exit 0;
> ruff/pyright at baseline. Codex mirrors regenerated (plan-analysis, critique-approach).
> **Batch D fully closed.**

### E. explore-ideas — 7 items
`fb-2026-07-11-022` + `-17-011` *(merge — same defect)*, `-17-003`, `-17-004`,
`-17-005`, `-17-002`, `-17-009`

The command currently produces hollow entities *and* corrupt provenance.

**`-17-009` belongs adjacent to Tier 0.** ~30% of `literature_anchors` from the
blind lens agents carry wrong authors/DOIs, and one DOI resolved cleanly to a
real but unrelated paper. Because `predates:` anchors are converted into
independent literature origins, this **misattributes provenance in the graph and
passes every automated checkpoint**. Cheapest real mitigation is the entry's own
option 2: have `resolve-anchors` cross-check title/first-author/year against the
resolved record and report a mismatch instead of resolving silently.

`--apply` writing template shells that `gaps` will not flag (`-11-022`/`-17-011`)
manufactured a false "metadata routing failure" diagnosis and a wasted task
(MM30 t877). `-17-003` and `-17-004` are explicitly filed as **design decisions,
not patch requests** — treat them as such.

> **Step 10 SHIPPED 2026-07-21, merged `--no-ff` local main `abb03608`.** All 7
> entries closed. Grounded against current main (several reports predated code
> that had evolved). Three owner design decisions were taken up front:
> `-17-004` → new `decision: fold` value (option b); `-11-022`/`-17-011` → apply
> **seeds** bodies from block material; `-17-003` → topics/themes stay
> **non-citable** (doc-only). Fixes:
>
> - **`-17-009`** (priority, provenance corruption): `resolve-anchors` now
>   cross-checks the anchor's stated title/year against the DOI/citekey-resolved
>   record and reports a new **`mismatch`** status (never `resolved`) when they
>   disagree — the valid-DOI-to-unrelated-paper shape no longer resolves
>   silently. Conservative (fires only on zero-shared-token titles). Plus agent
>   DOI/author self-verification (mit.1) and a command-doc "metadata is
>   model-generated" note (mit.3).
> - **`-11-022`/`-17-011`**: apply seeds the created entity's lead section with
>   `question_or_claim` + per-lens rationale (non-hollow); the `gaps` empty_body
>   check now compares the body against the **freshly-rendered scaffold for its
>   kind** (the real scaffold mixes multi-line HTML comments with placeholder
>   bullets, which the old line-scan let read as prose).
> - **`-17-004`**: `decision: fold` — apply writes no entity, emits a hand-fold
>   worklist item; `related_existing` names the target.
> - **`-17-005`**: malformed-YAML errors name the `candidate_id` (scanned from
>   the raw block even on parse failure) and the file-relative line.
> - **`-17-002`**: `idea-lens-researcher` gains an explicit search budget.
>
> Closes E in full (`-11-022`, `-17-011`, `-17-009`, `-17-002`, `-17-003`,
> `-17-004`, `-17-005`).

### F. Transient-artifact layer — 5 items
`fb-2026-07-17-001`, `-10-022`, `-10-021`, `-16-006`, `-10-020`

`-17-001` is a thorough design writeup and blocks the rest. The user's question
("should transient ledgers be version-controlled at all?") carries a real
constraint: `/science:curate` Phase 1 *requires* the prior ledger, so a naive
gitignore silently re-introduces the failure `fb-2026-05-01-003` exists to
prevent.

**This batch does not pre-select a location.** The entry's XDG analysis is
correct as far as it goes — `~/.cache` has regenerable-data semantics (a cache
sweep destroys carry-over history permanently) and `~/.config` has configuration
semantics, so `XDG_STATE_HOME` is the better of the three *XDG* homes. But that
ranking answers the wrong question, because **`XDG_STATE_HOME` does not satisfy
the persistence requirement the batch itself states**: it is strictly
single-machine, so it loses both fresh-clone reachability and peer visibility on
a Dropbox-synced tree edited by concurrent sessions. Ledgers are transient but
explicitly **not disposable**.

The real options are therefore:

| Option | Fresh clone | Worktrees | Peers | Cost |
|---|---|---|---|---|
| **A** — in-tree, untracked, resolved via `git rev-parse --git-common-dir` | no | yes (via indirection) | **yes** (Dropbox) | the indirection must be explicit or it silently recreates the worktree gap |
| **B** — `XDG_STATE_HOME/science/<project-id>/` | no | yes (no git indirection) | **no** | simplest; reuses the feedback-store resolver |
| **C** — tracked in-tree, excluded from the revision manifest | **yes** | yes | yes | status quo plus `revision_manifest_excludes`; keeps VCS noise |

The decision hinges on whether ledgers must stay peer-visible and reviewable. The
already-verified mitigation (`graph.revision_manifest_excludes`, manifest
880 → 876) makes **C** a legitimate do-nothing-further option, and the batch
should not be treated as blocked on relocating anything.

Two constraints on whichever option wins:

- **Prefer a `doc_kind`-keyed rule over path globs** (the entry's ask (b)). The
  transient/durable split is *not* directory-aligned: `doc/curations/` is
  homogeneous but `doc/meta/` mixes transient (`*-next-steps.md`) with durable
  (crosswalks, feasibility memos), which is why the working exclude had to be
  `doc/meta/*-next-steps.md` rather than `doc/meta/*`. Path globs re-hardcode the
  assumption that just proved wrong.
- **Any move of the feedback store needs a migration path.** `-17-001` argues the
  `~/.config/science/feedback` precedent is itself wrong-semantics and should move
  too. If that is adopted, it requires an explicit migration/export step for the
  existing records — including the 106 open entries this document triages, whose
  ids are referenced throughout it — plus a fallback read path for old locations.
  Relocating a durable queue is not a config change.

`-10-021` (unregistered `meta` kind spam) is a direct symptom of `-10-022`, so
fixing placement removes it. `-16-006` (worktree entries polluting
`~/.config/science/config.yaml`) is same-family.

`-10-021` (unregistered `meta` kind spam) is a direct symptom of `-10-022`, so
fixing placement removes it. `-16-006` (worktree entries polluting
`~/.config/science/config.yaml`) is same-family.

### G. `/science:curate` mechanics — 5 items
`fb-2026-07-10-017`, `-10-018`, `-10-019`, `-10-024`, `-10-023`

Low-risk; mostly doc/helper alignment. `-10-017` (helper payload diverges from the
command spec) and `-10-020` (the spec's own suggested frontmatter fails the
registered `curation-sweep` schema) are both "doc and code disagree".

`-10-023` is worth more than its `suggestion` category implies:
`days_since_last_review` is a **constant 365** on every row, so the freshness term
in attention ranking is dead weight — and both `curate` and `/science:review` lean
on it to pick reading targets.

### H. "Available on request" = dead data — 3 filings of one lesson
`fb-2026-07-17-010`, `-07-003`, `-17-008` *(positive)*

Merge into one. The argument is unambiguous: author-request data has no
procedure, no SLA, and no appeal, and fails third-party reproducibility *harder*
than an enclave (which at least publishes a followable procedure with a decidable
outcome). Wants a distinct `availability: on-request-only` value, exclusion from
default ranking, and a rule that it never satisfies a coverage requirement. Small
change; three independent reports.

### I. catalog-datasets — 2 items
`fb-2026-07-17-006`, `-17-007` (plus `-17-008` as a positive worth preserving as a
regression test)

`-17-006` is an inverted silent failure: six questions reported `no-candidate`
("no dataset exists") when the real cause was that none declared
`required_capabilities`, making them structurally incapable of ever scoring
covered. Wants a third gap class, `no-required-capabilities`.

### J. Pre-registration & design integrity — 8 items
`fb-2026-07-11-024`, `-11-025`, `-11-026`, `-11-027`, `-11-028`, `-11-033`,
`-18-007`, `-18-008`

Five are one natural-systems incident (t830) and are unusually high quality. Two
are mechanically enforceable and should both ship: **`-11-024`** (`git check-ignore`
every vehicle path a pre-registration names; fail closed) and **`-11-025`** (ask
whether the pipeline's own upstream rules regenerate the frozen input — the
conflict was visible in twelve lines of the Snakefile).

`-11-028` (a "blind erosion" protocol for when observed values leak early,
distinguishing *not conditioned on the null* from *blind*) is prescribed nowhere
and matters. `-11-027` is a **positive worth acting on**: freezing the full count
ledger — not just "244 models" but the row-sum distribution and full column-sum
vector — is what made the substitution legible as a tripwire and the
reconstruction provably faithful. The command's 1b guidance does not advertise
this.

### K. Estimand discipline — 11 items, all `skill:research`
`fb-2026-07-19-008` … `-19-014`, `-18-009`, `-18-010`, `-18-012`, `-18-013`

Largest methodology cluster and remarkably coherent: essentially one lesson with
eleven faces — *bind every number to its estimand (denominator, population,
outcome definition, endpoint type, control structure) and require estimand-match
before using it as support or dispute.*

Sub-lessons worth keeping distinct:

- Do not propagate an `[UNVERIFIED]` hedge as an assertion (`-19-008`)
- A task's paper→hypothesis link is a hint, not an evidence grade (`-19-009`)
- Authorization/execution status is ledger-and-artifact state, not recall (`-19-010`)
- Short follow-up is absence-of-evidence, never evidence-of-absence (`-19-011`)
- Do not reify one operationalization of a contested construct (`-19-012`)
- A multi-factor within-cohort contrast is confounded, not an isolated correction (`-19-013`)
- Non-detectability is an identifiability claim requiring a mixture-sensitivity argument (`-19-014`)
- Numerical proximity across non-commensurable estimands is not convergence (`-18-010`)
- A non-significant interaction is not demonstrated effect modification (`-18-013`)

`-18-009` makes the sharpest structural point: citation-verification agents caught
number and paper errors but **not** scope mismatches, because they checked *"is the
number real"* rather than *"does the number at its scope support the claim"*.

**Recommendation: one new skill leaf with a named, runnable check — not eleven
bullets appended to `skill:research`.**

### L. Statistics / estimator certification — 9 items
`fb-2026-07-13-001`, `-13-002`, `-13-003`, `-12-010`, `-12-011`, `-12-012`,
`-12-013`, `-12-014`, `-12-015`

Mostly the cancer-evolution t079 arc; maps onto the existing estimator doctrine.

`-12-010` is the flagship: *"zero divergences" is a gate that cannot fail* — a run
with 0 divergences in 1200 draws had treedepth saturated on 99.8% of iterations,
R-hat to 1.50, and bulk ESS of 4. Wants a **posterior-computation leaf** for
estimator-certification; the four axes map cleanly.

`-13-001`/`-13-002` are one lesson: benchmark at the geometry that will execute,
and never take the max across configurations — *"a cost gate that can only be made
to pass by a favourable measurement choice is not a gate."*

`-12-013` generalises beyond statistics: a hand-rolled decision-bearing diagnostic
needs known-answer tests **including a benign case**, because its bug (4) —
k-hat returning `+inf` for the *ideal* proposal — is invisible to every
adversarial test case. This is the same lesson Finding 1 re-teaches.

`-12-011` (pre-commit a bounded number of qualitatively distinct inference
escalations; make "computationally non-identifiable at available resources" a
nameable **verdict**) is a strong process addition.

### M. Feedback / post-mortem system — 3 items
`fb-2026-07-18-011`, `-11-029`, `-16-001` — detailed in the next section.

### N. Singletons & small fixes — 23 items

**Ship-today tier.** `-16-001` (`feedback show`), `-16-002` (`science projects`),
`-18-006` (commons ref resolution is indentation-sensitive: 2-space `- topic:X`
dangles while 0-indent resolves; both are valid YAML, so it is a resolver quirk),
`-07-001` (`tasks edit --related` appends instead of replacing *and* accepts
non-canonical short IDs that later fail graph validation — two bugs compounding),
`-12-001` (4 feedback-CLI tests read the ambient telemetry store, so they pass or
fail on wall-clock), `-11-007` (add `theme` to the shared commitlint enum — every
other entity kind is already there), `-18-001` (move the PDF-first branch above
the paper-fetch block), `-11-008`/`-11-009` (add-theme guidance and a positive).

**Needs a small design call.** `-16-003` (getattr-based field audits misfire under
`extra=allow` — D5 aftermath; wants a distinct `undeclared_key` diagnostic, and
the adjacent `workflow`/`commits_to`/`blocked_by` audits share the pattern),
`-19-004` (composite build parses siblings' `science.yaml` with the *local* schema,
so one project's pin bump breaks every older-pinned sibling — with a pydantic
error naming the wrong project), `-08-002` (orphaned-executable fires on every
Snakefile-referenced script, training reviewers to ignore the class),
`-08-003` (`science payload pin` primitive), `-10-004` (manifest/directory
payload concept), `-19-015` (slug truncation — see note below), and
**`-07-002` + `-08-001` together** (the `review-pipeline` 9-dimension rubric is
graph-inquiry-shaped: dimensions 4/8/9 assume BoundaryIn/BoundaryOut, tensor
shapes, and a workflow output dir, so reviewing a prose `kind:plan` or an
already-completed simulation needs substantial reinterpretation — wants a
per-dimension gloss or a parallel rubric variant, plus a note recommending an
independent reviewer for self-authored targets).

**Environment lore → docs, not code.** `-10-001` (the sandbox *stalls* Snakemake
fetches into an unkillable deadlock rather than cleanly blocking them), `-10-002`
(`fetch_url.py` has no total-download watchdog; `timeout=` is per-read, so 9 MiB
partials froze for 12h), `-10-003` (`--retries` deadlock), `-10-005`
(affy/preprocessCore `pthread_create` EINVAL → pure-R RMA recipe).

**Agent-prompt fixes.** `-10-025` (cap concurrent PDF-heavy subagents at ~5;
prefer `pdftotext`), `-10-026` (`kind:` not `type:`; never emit retired
`datasets:`).

**Project-local, not toolkit.** `-18-002` (MM30 template drift).

> **Note on `-19-015`:** the earlier `truncate_slug_on_word_boundary` fix
> (fb-2026-05-23-003) solved *mid-word* truncation. This report is a distinct,
> unsolved problem — word-boundary truncation still drops the semantically
> discriminating tail (`…formula-catalogs-are` lost `near-disjoint`). Not a
> regression; a second-order gap. Wants token-selection or a pre-write prompt.

---

## The feedback / post-mortem system itself

> **Step 2 (feedback store non-lossy) SHIPPED 2026-07-21, branch
> `feedback-nonlossy`.** Points 1 and 2 below are done in the order Finding 0
> mandates: non-lossy `occurrences[]` first, then normalised-exact matching, then
> advisory-only fuzzy, then `feedback targets`, plus `feedback show`. Points 3–5
> (post-mortem framing, unreflected-failure surfacing, positives→tests) are Batch
> M remainder (sequence step 9), not part of this step.

1. **Fix `find_duplicate`** — highest leverage in the backlog (Finding 0). **DONE.**
   `recurrence` is now derived (`len(occurrences)`); a re-filing appends a
   `FeedbackOccurrence{date,project,category,detail}` instead of incrementing an
   integer and discarding the filing (the old destructive `dup.recurrence += 1` is
   gone). `find_duplicate` compares a *normalised* target (`normalize_target` folds
   `command:`/`commands:`/`cli:`/`science:` and collapses whitespace); the summary
   substring check stays as the conservative exact-ish signal. Fuzzy matching is
   **advisory only** — `find_similar_open` surfaces near-neighbours after the entry
   is filed and `--merge-into <id>` performs an explicit non-lossy merge; nothing
   is ever auto-merged on a fuzzy match. **`science feedback targets`** lists
   existing target spellings (raw + normalised key + counts) so a filer reuses one.
   Legacy entries migrate on load (backfill one occurrence, count preserved); all
   429 live entries are `recurrence:1` so migration is exact. `concern` equality is
   kept as a hard partition (distinct concern = distinct entry) — the corpus relies
   on it (`test_find_duplicate_distinguishes_concern`), so it was *not* demoted.

2. **`science feedback show ID`** (`-16-001`) — **DONE.** Dumps the full entry as
   YAML including every recorded occurrence. (`--full` on `list` not added — `show`
   covers the triage need this item was filed for.)

> **Step 9 (Batch M remainder) SHIPPED 2026-07-21, branch `feedback-batch-m`.**
> Points 3–5 below are done: post-mortem gained the fourth trigger class; both
> `next-steps` and `status` gained a mandatory self-improvement-loop scan
> (unreflected failures → `/science:post-mortem`; unconsumed positives →
> `feedback regression-candidates`/`scaffold-test`); and the positives
> consumption path is a new `science feedback regression-candidates` command
> reusing the existing `scaffold-test` machinery. Closes M[`-18-011`, `-11-029`].

3. **Widen post-mortem's entry framing** (`-18-011`) — **DONE.** `commands/post-mortem.md`
   "When to use" gained a fourth trigger: *a synthesized claim/verdict overstated
   relative to what its cited evidence supports (scope/estimand/population/strength
   mismatch), caught in review* — the Batch K failure class. The reflection steps
   are mapped in place (step 1 = claim-vs-evidence-at-scope gap; step 3 = the
   estimand-match/scope check that would have caught it).

4. **Nothing prompts post-mortem** (`-11-029`) — **DONE (cheapest useful version).**
   `next-steps` (new mandatory §3f) and `status` (§6) now surface **unreflected
   failures** — a pre-registration deviation amendment, a gate failure /
   `inconclusive-for-protocol` verdict, or a discarded/superseded/`draft` run —
   defined as *reflected once a feedback entry references it*, cross-checked via
   `science feedback list --project <p> --format json`, and prompt
   `/science:post-mortem` for each. The report's costlier options (1) interpret-results/validate
   nudges and (2) pre-reg-template amendment note remain unimplemented by design —
   step 9 took the cheapest surface-in-next-steps/status option the design mandated.

5. **Positives have no consumption path** — **DONE (mechanism).** New
   `science feedback regression-candidates` command lists open `positive` entries
   with the existing-test file each should scaffold into
   (`_suggested_next_test_target`, now target-normalized so `cli:`/`science:`
   spellings route like `command:`), reusing the already-present `feedback
   scaffold-test`. Wired into `next-steps` §3f and `status` §6. The three specific
   positives (`-17-008`, `-11-009`, `-11-027`) live in Batches H/I, N, J — step 9
   builds the consumption path; those batches close the entries.

---

## Blocking design decisions

Two decisions gated multiple batches. **Both resolved by the owner 2026-07-21**
(sequence steps 3 and 4); the rulings below are what steps 7 and 8 implement.

### D1 — Per-field ownership and merge policy — RESOLVED 2026-07-21

**Scoping correction from the grounding pass: the ownership table is not a
greenfield deliverable.** Every commons field already carries a `science:merge`
policy annotation in the base + kind-mixin JSON Schemas (`replace` / `append` /
`forbidden` / `project_only`), and both the overlay allow-list and the
promote-time classifier already derive from those annotations
(`science/model/src/science_model/entity_schema/merge.py:21-57`,
`science/src/science_tool/commons/promote.py:1928`). So D1 is **not** "author a
table for ~40 fields" — it is exactly two moves: **(i) add one missing policy
value, `override`, and (ii) reclassify the three contested fields.** Every other
field keeps its existing annotation.

Rulings (owner-confirmed):

| Field | Class (ruling) | Current code | Overlay schema change | Promote builder change |
|---|---|---|---|---|
| `provided_capabilities` | **canonical** | in no schema → dropped at promote (`promote_dataset.py:269-286`) | none — overlay carries nothing | add the field to `mixin-dataset` with `science:merge: replace`; it then routes to the canonical bucket instead of `_dataset_dropped_fields` |
| `tier` | **canonical-with-override** | canonical + required (`mixin-dataset-2.0.json:13`), no override path | add optional `tier` + `tier_rationale`, both annotated `science:merge: override` (overlay-1.1 → 1.2) | canonical `tier` still promoted (unchanged); an overlay `tier` never flows back |
| `paper_kind` | **project-only** | canonical (`mixin-paper-2.0.json:19`), promoted | add `paper_kind` to the overlay allow-list, annotated `project_only` | remove from `mixin-paper` canonical (2.0 → 2.1); the classifier's existing default then routes it to the overlay bucket |

**The new `override` class — precedence rules** (the only net-new mechanism):

1. **Resolution.** When both the canonical and the overlay carry the field, the
   **overlay value wins**; when the overlay omits it, the canonical value is
   used. (Contrast `project_only`, which has no canonical counterpart, and
   `replace`/`append`, which never appear on an overlay.)
2. **Rationale requirement.** An overlay `override` field whose value **differs**
   from the canonical and carries no companion `*_rationale` = **WARN** (silent
   divergence). An overlay `override` field **equal** to the canonical value =
   WARN "redundant; matches canonical, remove."
3. **One-way.** An `override` value is local-only and is **never** written back to
   the canonical at promote — `promote.py` treats it like `project_only` on the
   write path but like a shadowing scalar on the read/merge path.

**Migration.** `provided_capabilities` populates by re-promote (or a backfill
copying the live project-local value onto the canonical). `-11-020`/`-11-021`
(canonicalization lossiness) fold in here: `-11-021` already fixed (`29ffdea4`);
`-11-020` is the residual constraint and is satisfied by the same "derive overlay
+ promote from one annotated schema" mechanism this ruling standardizes.

**Step 7 SHIPPED — implementation notes (correction from further grounding).** The
D1 core landed on branch `batch-a-d1`. Two of the three "Overlay schema change" /
"Promote builder change" cells above were **refined once the code was read
line-by-line**, both in the direction of *less* churn:

- `paper_kind` is **not** removed from `mixin-paper` and needs **no commons
  migration**. The mixin already classifies `created`/`updated`/`status` as
  `science:merge: project_only` (fields modeled on the mixin but never promoted);
  `paper_kind` simply **joins them** — one annotation added in place, no 2.0→2.1
  bump. Removing it would have *broken* project papers (the composed **project**
  profile is closed, and `paper_kind` lives on project `entities/papers/*.md`),
  and the "backfill before removal" migration the row anticipated is moot because
  the field is never removed. Commons is `extra="allow"` (only `hypothesis` is in
  `PROJECT_MIXIN_NAMES`), so the 23 canonicals that still carry `paper_kind` keep
  it harmlessly and future promotes stop writing it. `paper_kind` is **also**
  added to the overlay allow-list (overlay-1.2, `project_only`) so a consumer may
  carry its own.
- `provided_capabilities` is added to `mixin-dataset-2.0` in place (default
  `replace` → canonical bucket); no version bump needed (the field was previously
  *dropped*, so admitting it is purely additive).
- `tier`/`tier_rationale` land on **overlay-1.2** with the new `override` policy,
  as specified. Precedence subtlety made explicit in code: `tier` is `replace` on
  the dataset **mixin**, so `lookup_merge_policy` had to be taught that an
  overlay-declared `override` **wins over** the entity schema's policy for the
  same field name (override is inherently an overlay↔canonical relationship).
- The **rationale WARN** (rule 2) is emitted by `override_divergence_warnings`
  (pure) and surfaced by `validate_project_overlays` → `science commons validate
  --project` (the only surface that has both canonical and overlay in hand).

Closes `-09-001`, `-18-005`, `-11-001`; confirms already-shipped `-11-021`
(schema now declares `Methods`), `-11-018`/`-16-004` (federation_guard +
promote_body_loss wired into promote).

**Batch A REMAINDER SHIPPED 2026-07-21 (branch `batch-a-remainder`, merge
`b2e71b56`, local main, unpushed).** Grounding overturned the design doc twice:
two of the six were already fixed, and one no longer reproduces in data. Owner
decisions taken via AskUserQuestion (recommendation-first) for the three
genuine forks.

- **`-16-005` — already fixed, closed with note.** Both silent failures landed
  in the Tier-0 commons work: part 1 (overlay inert when a deferring adapter
  like `bib` owns the id) at `5d1a25fc` ("close commons overlays before identity
  arbitration" — `validate_overlay_pin` now runs for every resolved overlay);
  part 2 (suppressed registry-staleness warning on the graph load path) at
  `198c2c37`/merge `2fddebb9` (warn-once). Report predates both.
- **`-12-006` — already fixed, closed with note.** The D1 migration to `2.0`
  mixins annotates `status` as `project_only`, and `read_overlay_merge_policy`
  defaults un-annotated overlay fields to `project_only`, so overlaying `status`
  now resolves cleanly through `resolve_field`'s PROJECT_ONLY branch. All 274
  commons papers + all datasets are `2.0`; the "unreachable" comment is gone.
  Only a hypothetical `1.0`-mixin canonical (zero exist) would still raise.
- **`-11-019` — new `commons.overlay-local-duplicate` check (ERROR).** Flags an
  id held as BOTH a local `entities/` owner and an `overlays/` overlay — always
  a duplicate; commons-independent (a purely local fact). Fires 0 across the
  23-project fleet, so ships at ERROR. `commons_owner_collision` defers to it
  when a project overlay exists, so the two never give conflicting advice (its
  "convert to an overlay" is wrong when one already exists).
- **`-12-007` — commons status check (WARN).** `CommonsValidator` now checks
  each record's status against its kind vocabulary (`valid_statuses`) and warns
  — never errors, since the vocabulary is uncertified for commons. Certified on
  `~/d/science-commons`: fires on exactly the one `exploratory` dataset.
- **`-19-005` — promote-paper guard (owner: refuse).** `plan_promote` fails
  closed when a promoted paper's `dataset_usage` references a dataset with no
  commons canonical (the toolkit half of the hand-fix to commons Kotliarov2020).
  Chosen over allowing datapackage-less datasets in commons or a silent audit
  WARN.
- **`-11-020` — promote-time completeness gate (owner: gate + decline
  semantic).** Warns when a promoted paper canonical lacks Methods/Limitations
  (a measure, never a block). The two semantic asks (claim-in-body,
  overlay-contradicts-canonical) are deliberately NOT built — no check can fire
  on them honestly.

Full suite + snapshot + real_projects + model all exit 0; ruff/pyright at the
pre-existing baseline (4 ruff in untouched `test_numeric_binding.py`; 7 pyright
in untouched files). **Batch A fully closed.**

### D2 — The transient-state home — RESOLVED 2026-07-21: Option C (ratify status quo)

Ledgers must stay **peer-visible and reviewable** — they are reviewed, they carry
forward carry-over history, and `/science:curate` Phase 1 requires the prior
ledger — so the per-operator `XDG_STATE_HOME` option B is out. Between the two
peer-visible options, **C is already built, shipped, and verified**:
`graph.revision_manifest_excludes` (default `()`, applied by `fnmatch` at
`graph/io.py:398-410`) filters tracked files out of the revision manifest, and
post-acute-infection sets `doc/curations/*.md` + `doc/meta/*-next-steps.md`
(manifest 880 → 876, `graph diff` empty, `validate` unchanged). Option A (in-tree
untracked + `git rev-parse --git-common-dir`) is net-new plumbing with no
precedent in the codebase and **loses fresh-clone reachability** for no gain over
C. Ruling: **do nothing to relocate.**

Consequences for **step 8 (Batch F)**:

- **No relocation, and the `science feedback` store does NOT move.** It is a
  durable global queue at config-home (`~/.config/science/feedback`, already
  XDG-aware via `get_science_config_dir`, `registry/config.py:31-42`), not
  transient scratch; moving it would force migrating the 106+ ids this document
  references for zero reachability gain.
- **Ship a default exclude set in the toolkit** so every project inherits the
  ledger excludes instead of rediscovering the knob (post-acute-infection is
  currently the *only* project that sets it). Candidate default:
  `doc/curations/*.md`, `doc/meta/*-next-steps.md`.
- **`doc_kind` is deferred, not adopted.** It does not exist in the model (only
  the unrelated entity-kind `CurationScope` does); the "prefer `doc_kind`-keyed
  rules over path globs" rider is a separate modeling change and is **not** a
  prerequisite for C. Path globs remain the mechanism.
- **Fix the curate-doc drift.** `commands/curate.md` Phase 1 still points its
  required prior-ledger read at the pre-relocation `entities/meta/curation/`
  path while real projects have moved to `doc/curations/`. Correct it in step 8.

**Step 8 SHIPPED 2026-07-21 (branch `batch-f-transient`, merge `395b5296`, local
main, unpushed).** Two deliverables, both grounded on the real post-acute-infection
ledger before coding:

- **Default exclude set** — `graph/io.py::DEFAULT_REVISION_MANIFEST_EXCLUDES =
  ("doc/curations/*.md", "doc/meta/*-next-steps.md")`, unioned (dedup,
  defaults-first) into `_revision_manifest_excludes`; a project's own list adds to
  the defaults, and post-acute-infection's explicit copy is now idempotent. The
  next-steps glob is `*-next-steps.md` (suffix) because the adopted convention is
  `<date>-next-steps.md`, **not** the toolkit `next-steps.md` command's documented
  `<NNNN>-next-steps-<date>.md` — a live drift folded into `-10-021`, left open.
  3 TDD tests; snapshot + real_projects both exit 0 (no real project's manifest
  shifted — the one that has ledgers already set the knob).
- **curate.md** — the 4 `entities/meta/curation/` path references → `doc/curations/`,
  and the Phase-4 frontmatter → the verified project form (`doc_kind`/`title`/
  `sweep_scope` + a "not a KG entity" body marker, no `kind:`/`id:`). This dissolves
  `-10-020` (graph audit no longer schema-validates the ledger — it is not an entity)
  and `-10-022` (placement). Codex mirror `science-curate/SKILL.md` regenerated.

**Deferred out of step 8 (not D2 consequences — needed their own decisions), then
SHIPPED as the Batch-F remainder 2026-07-21 (branch `batch-f-remainder`, merge
`bce0dbe4`, local main, unpushed), owner-confirmed via AskUserQuestion:**

- **`-10-021` — relocate next-steps to `doc/meta/`.** `/science:next-steps` +
  `templates/next-steps.md` prescribed `kind: meta` files under scanned
  `entities/meta/`, but `meta` is unregistered, so every load logged "unknown entity
  kind meta". These files materialize zero triples (transient prose), and the
  validate gap-analysis check *already* reads next-steps from `doc/meta/next-steps-*.md`
  — the command and its own consumer were inconsistent. Fix: move the write path to
  `doc/meta/next-steps-<date>.md` with `doc_kind: "meta"` (not entity `kind`), drop
  the `<NNNN>-` prefix, remove the false "validator rejects kind:meta outside
  entities/meta/" claim (no code enforces it), drop the stale `entities/meta`
  gitignore line from `create-project.md`. Chosen over registering `meta` as a kind
  (would legitimize misclassified content) or silencing the loader (would patch the
  validator to be permissive). Grounding correction: the design doc's "-10-021 is a
  symptom of -10-022" claim does not hold — the curation-ledger fix does not touch
  next-steps files; and the legacy `entities/meta/explorations` half was already
  fixed forward (explore-ideas now writes `doc/explorations/` frontmatter-less).
- **`-16-006` — register the main checkout, not the linked worktree.** `science
  graph build` auto-registered the cwd; run from `.worktrees/<name>/` it added the
  worktree path, and because the worktree shares the project's `science.yaml` id,
  `registry_root_for_id` then raised "ambiguous" and broke commons promote/overlay.
  Fix: new `resolve_registration_root` maps a linked-worktree root to its
  main-checkout equivalent (via `git worktree list`, relative-path preserving);
  `build_project_graph` registers that. Chosen over skip-in-worktrees (leaves the
  project unregistered if you only build from worktrees) and dedup-by-id+prune
  (doesn't stop the entry being written). **Batch F now fully closed (5/5).**

---

## Proposed sequence

Every batch appears exactly once. Bracketed ids are the specific items a step
closes when it does not close a whole batch.

| # | Work | Closes | Gated on |
|---|---|---|---|
| 1 | **Tier 0** — silent corruption. Three independent branches (commons, inquiry-export, pre-registration-vehicle); they share no code. **inquiry-export DONE** (`fix/inquiry-export-uri`); commons and pre-reg-vehicle outstanding. | A[`-16-004`, `-16-005`, `-11-018`], B[`-19-001` ✅, `-19-003` ✅ demoted], J[`-11-024`] | — |
| 2 | **Feedback store non-lossy** — `occurrences[]`, then normalised-exact target matching, advisory fuzzy, `feedback targets`, `feedback show`. **DONE** (branch `feedback-nonlossy`). | M[`-16-001`] ✅ | — |
| 3 | **Decision D1** — per-field ownership & merge-policy table (Batch A). **RESOLVED 2026-07-21**: `provided_capabilities`→canonical, `tier`→canonical-with-override (new `override` policy value), `paper_kind`→project-only; the table already exists as `science:merge` annotations, so D1 = add one policy value + reclassify 3 fields. | — | owner ✅ |
| 4 | **Decision D2** — transient-state home (Batch F options A/B/C). **RESOLVED 2026-07-21**: Option C (ratify status quo) — no relocation, feedback store stays put, ship a default exclude set, defer `doc_kind`, fix `curate.md` Phase 1 path drift. | — | owner ✅ |
| 5 | **Batch B remainder** + the generic "declared-key-materialises-zero-triples" lint. **DONE 2026-07-21** (branch `batch-b-remainder`): the generic lint already existed (narrow, kind-aware) and its general form was deliberately rejected — nothing built; `-12-002`/`-18-004`/`-11-017` pt2-3 already fixed; `-12-003` premise stale; real fixes = `-12-009` freeze-status gate + `-11-017` pt1 evidence-line template docs + `-18-003` confirmed already-addressed. | B (rest) ✅ | — |
| 6 | **Batches K and L** — two skill leaves. No code risk; parallelisable with 1–5. | K, L | — |
| 7 | **Batch A remainder** — overlay schema + promote builder derived from D1; federation-awareness pass; close `-11-021`. **D1 CORE SHIPPED** (branch `batch-a-d1`): `provided_capabilities`→canonical, `tier`→override (new policy value, overlay-1.2, rationale WARN), `paper_kind`→project-only (annotate-in-place, no commons migration); federation-awareness (`-11-018`/`-16-004`) + `-11-021` confirmed already shipped. **REMAINDER SHIPPED 2026-07-21** (merge `b2e71b56`): `-16-005`/`-12-006` already-fixed (closed with notes); `-11-019` new `commons.overlay-local-duplicate` ERROR check; `-12-007` commons status WARN; `-19-005` promote-paper guard (refuse dangling dataset_usage); `-11-020` promote-time Methods/Limitations completeness warning (semantic asks declined). **Batch A fully closed.** | A ✅ | D1 |
| 8 | **Batch F** — implement the chosen home; `doc_kind`-keyed excludes; migration if the feedback store moves. **D2 CORE SHIPPED 2026-07-21** (branch `batch-f-transient`, merge `395b5296`): default revision-manifest exclude set (`doc/curations/*.md`, `doc/meta/*-next-steps.md`) unioned into `_revision_manifest_excludes`; curate.md ledgers moved to `doc/curations/` with `doc_kind`/`sweep_scope` (not the entity `kind`/`scope` that failed the curation-sweep schema). `doc_kind`-keyed excludes deferred (path globs remain); no feedback-store move. **Closed `-17-001`, `-10-022`, `-10-020`. Remainder SHIPPED 2026-07-21 (branch `batch-f-remainder`, merge `bce0dbe4`): `-10-021` next-steps → `doc/meta/` with `doc_kind` (matches the gap-analysis reader); `-16-006` `resolve_registration_root` registers the main checkout not the linked worktree. **Batch F fully closed (5/5).** | F ✅ | D2 |
| 9 | **Batch M remainder** — post-mortem fourth trigger class; unreflected-failure surfacing in `next-steps`/`status`; positives → regression tests. **DONE** (branch `feedback-batch-m`). | M[`-18-011` ✅, `-11-029` ✅] | 2 |
| 10 | **Batch E** — `resolve-anchors` metadata cross-check first (`-17-009` is provenance corruption), then the apply/gaps defects, then the two design questions. **DONE 2026-07-21** (`abb03608`): `mismatch` status + agent verify; body seeding + scaffold-aware empty_body; `decision: fold`; candidate-named YAML errors; agent search budget; topics/themes stay non-citable (doc). | E ✅ | — |
| 11 | **Batch C** — inquiry-subsystem design pass. **DONE 2026-07-22** (branch `batch-c-inquiry`, merge `4525887a`): `estimand_type` on InquiryProfile + exporter gating (`-19-007`); `inquiry import` clean-fail via `has_compiled_subgraph` (`-11-031`/`-11-032`); validate `no_inquiry_block` INFO vs `no_inquiry_subgraph` WARN split (`-11-030`); critique-approach report → `entities/interpretations/` (`-19-002`) + `science dag` port doc (`-19-006`). | C ✅ | 1 |
| 12 | **Batch D** — after auditing `status-vocab-certification`. **DONE 2026-07-22** (branch `batch-d-status`, merge `5ce079ec`): audit found the branch's work already merged via D5 `537f52c1`, so `-11-034` is addressed (per-kind `severity_for_kind`, only hypothesis ERROR; layout_version axis deleted; vocabularies widened) — closed with note; `-12-008` readiness() accepts {done,complete,answered,committed,amended}; `-12-004`/`-12-005` command docs stop prescribing out-of-vocabulary statuses. | D ✅ | branch audit |
| 13 | **Batch J remainder**, **G**, **H**, **I**. **DONE 2026-07-22**: **H+I** (merge `e8c99927`) — on-request-only availability is analysis-ineligible (readiness not-ready, weight 0, plan_gate refuses; `verify-access --on-request-only`; `_coerce_access` availability-drop bug fixed) + `no-required-capabilities` unscoreable-target coverage (reuses `missing-required-capabilities`) + Step-6 authorization gate; **G** (merge `3f4e961e`) — provenance-aware `missing_source_refs` + tolerant decision-digest parser (`-10-017` already-accurate, `-10-023` doesn't-reproduce, **`-10-024` structured-ledger DEFERRED, still open**); **J-rest** (merge `2239011a`) — 7 pre-registration/design-integrity guidance additions. | J (rest) ✅, G ✅ (−024 deferred), H ✅, I ✅ | — |
| 14 | **Batch N** — ship-today tier first; then the design-call items; then docs/lore and agent-prompt fixes. | N | — |

Steps 3 and 4 are decisions, not implementation, and can be taken now or at the
gate; nothing before step 7 depends on either.

## Cautions for implementers

- **Check unmerged branches first.** Batch D is likely half-done on
  `status-vocab-certification`. Much recent toolkit work sits on *local* `main`
  unpushed, and a consumer project pinned to the public Git source cannot see it —
  verify which toolkit a reporting project actually ran before trusting or
  re-implementing any finding.
- **`fb-2026-07-16-005(d)`**: ~~fixing the overlay-pin bug is a breaking change for
  existing pins; refresh cancer/meta's in the same change.~~ **Retracted
  2026-07-20 — no refresh needed.** All 292 pinned overlays already match their
  commons canonical; the current toolkit validates them green. See the retraction
  under the Tier 0 sequencing constraint for the audit.
- **Finding 1 is a cautionary tale about this document too.** A prior triage
  marked that item fixed on the strength of a test that could not fail. Where this
  document asserts a defect is real, it was verified by execution; where it
  summarises a report, it is labelled as such.

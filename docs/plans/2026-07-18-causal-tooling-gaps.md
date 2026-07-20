# Causal tooling gaps — capture (no fixes this session)

Date: 2026-07-18
Status: tracked; not scheduled (amended 2026-07-20 — see the retraction below)

Surfaced while pulling baygent causal material and sweeping consumer projects
(multiple-myeloma, post-acute-infection, natural-systems). These keep projects
*outside* the toolkit's causal machinery and cause reinvention.

## Open gaps

1. **pgmpy optional → silent skip (fail-open).** `validate_inquiry`'s
   identifiability / adjustment-set checks `skip` when `pgmpy` is not installed
   (post-acute, MM), contradicting the "a check must be able to fail" doctrine.
   Adjacent: fb-2026-05-24-005.
2. **`inquiry import` status-vocab crash.** Pydantic `ValidationError` on MM's
   inquiry statuses (`active`/`descriptive`/`draft`) vs the toolkit's
   `sketch|specified|…`. MM fb-2026-07-11-031 / -032.
3. **Unpopulated documented edge schema.** The edge `identification:` / `posterior:`
   schema in `references/dag-two-axis-evidence-model.md` has no tooling to populate
   or validate it, so MM hand-transcribes via `_add_identification.py` /
   `_add_posteriors.py`.

## ~~Not a current bug (verified 2026-07-18)~~ — RETRACTED 2026-07-20

> **This section was wrong.** It is retained, struck through, as a record of how
> the verification failed. The corrected finding is gap 4 below.

The original claim was: the suspected `export-pgmpy` "empty edge list from a
named-graph mismatch" is *already fixed* — `causal/export_pgmpy.py` reads the
per-inquiry named graph and unions it with `graph/causal`, covered by
`tests/test_causal.py::TestExportPgmpy::test_export_pgmpy_reads_compiled_patch_inquiry_edges`
(reran green) — so the post-acute note reflects an older pinned toolkit.

**Why it was wrong.** The union *is* present and *is* a real fix, but it is
gated behind an empty member set, so verifying the union did not test the
reported defect. And the cited test cannot fail — twice over:

1. **Its fixture writes the reader's URI convention, not the writer's.**
   `test_causal.py::_build_compiled_inquiry_graph` hardcodes
   `normalize_slug=True`, and its own docstring says so: *"the causal tests use
   hyphenated slugs and rely on the retired `add_inquiry` mutator's `_slug`
   normalization so the readers resolve the same inquiry URI."* Production
   compilation (`inquiry_compile.inquiry_uri`) does **not** normalise, so no test
   exercises the real URI.
2. **Its assertion is vacuous.** It asserts `'("x", "y")' in script`, but the
   generated script always ends with
   `ci.get_all_backdoor_adjustment_sets("x", "y")` when treatment is `x` and
   outcome is `y` — so the assertion passes **even when the model is
   `DiscreteBayesianNetwork([])`**. Confirmed by running the
   `normalize_slug=False` case: assertion green, model empty.

This is the `fb-2026-07-11-021` defect class (a test that asserts an artifact's
own wording and thereby certifies a phantom) recurring *inside the verification
of another instance of it*.

## ~~Open~~ gap 4 — `export-pgmpy` inquiry-URI mismatch — FIXED 2026-07-20

Verified empirically 2026-07-20 against `main`, then fixed on branch
`fix/inquiry-export-uri`: the exporter now resolves through
`store/inquiry.py::resolve_inquiry` (discovery, extracted from `get_inquiry`)
instead of reconstructing the URI. The vacuous assertion was replaced with a
parsed-edge-list check and a production-convention fixture. Full suite green
(9475 passed); ruff/pyright unchanged from baseline.

The original diagnosis, retained:

| | Construction | Result for a hyphenated slug |
|---|---|---|
| **Writer** — `graph/inquiry_compile.py::inquiry_uri` | `PROJECT_NS["inquiry/" + canonical_id.split(":")[-1]]`, hyphens **preserved** | `inquiry/compound-boundary-conditions-…` |
| **Reader** — `causal/export_pgmpy.py:103` | `_slug(slug)` → `[^a-z0-9]+` replaced with `_` | `inquiry/compound_boundary_conditions_…` |

The reader resolves an empty graph → `members` is empty → the member filter at
`export_pgmpy.py:154` drops every edge, **including the ones unioned in from
`graph/causal`**. Measured:

    MODEL EDGE LIST for normalize_slug=True  : '("x", "y"),'
    MODEL EDGE LIST for normalize_slug=False : ''          # DiscreteBayesianNetwork([])

`_get_causal_edges_for_inquiry` returns **0 edges** for any hyphenated slug —
i.e. for essentially every real patch-definition. Reported as
`fb-2026-07-19-001`.

**`fb-2026-07-19-003` does not reproduce.** Its escalation — with `pgmpy`
installed the identifiability checks come back *green* over the empty model — was
tested directly and does not occur: `validate_inquiry_dataset` resolves via
`_discover_inquiries` (a different path from the exporter) and returns
`skip` / "No causal edges found". A regression guard now locks that invariant in,
mutation-tested. Gap 1 above remains the real fail-open on this surface: without
`pgmpy` the checks skip, which is a *different* uncertified-instrument problem.

Fix direction and the authored-vs-resolved reconciliation that should replace a
naive "fail on zero edges" are specified in
[`2026-07-20-feedback-triage-2026-07-batch-design.md`](2026-07-20-feedback-triage-2026-07-batch-design.md)
(Finding 1, Batch B). Note that gap 1 above is the *same* fail-open surface
viewed from the dependency side.

## Feature opportunities

- A command to **attach a Bayesian fit result to an inquiry edge** (populate the
  documented `posterior:` block), retiring MM's hand-transcription.
- A **canonical causal-evidence-ledger schema** — three bespoke ones exist across
  MM and post-acute.

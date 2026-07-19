# Causal tooling gaps — capture (no fixes this session)

Date: 2026-07-18
Status: tracked; not scheduled

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

## Not a current bug (verified 2026-07-18)

The suspected `export-pgmpy` "empty edge list from a named-graph mismatch" is
**already fixed** in the current toolkit — `causal/export_pgmpy.py` reads the
per-inquiry named graph and unions it with `graph/causal`, covered by
`tests/test_causal.py::TestExportPgmpy::test_export_pgmpy_reads_compiled_patch_inquiry_edges`
(reran green). The post-acute note reflects an **older pinned toolkit**; this is a
downstream pin/upgrade, not an open fix.

## Feature opportunities

- A command to **attach a Bayesian fit result to an inquiry edge** (populate the
  documented `posterior:` block), retiring MM's hand-transcription.
- A **canonical causal-evidence-ledger schema** — three bespoke ones exist across
  MM and post-acute.

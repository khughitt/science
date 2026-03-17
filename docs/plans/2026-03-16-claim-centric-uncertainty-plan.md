# Claim-Centric Uncertainty Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace edge-as-fact and hypothesis-status-first assumptions with a skeptical, claim-centric uncertainty model across the Science graph, CLI, templates, and guidance.

**Architecture:** Keep `question`, `hypothesis`, and `inquiry` as user-facing structures, but make `claim` and `relation_claim` the primary units of belief. Evidence should attach to claims, uncertainty should be derived from aggregated support and dispute, and higher-level views should summarize claim state rather than pretend edges or hypotheses are established facts.

**Tech Stack:** Markdown command/template docs, Click CLI, rdflib dataset queries/materialization, Pydantic source models, marimo/Polars graph visualization, pytest.

---

### Task 1: Publish The Canonical Reasoning Model Reference

**Files:**
- Create: `docs/claim-and-evidence-model.md`
- Modify: `docs/plans/2026-03-16-claim-centric-uncertainty-design.md`
- Test: none

**Step 1: Write the reference document**

Create `docs/claim-and-evidence-model.md` with:

- definitions for `question`, `hypothesis`, `claim`, `relation_claim`, `evidence_item`, `study`, `result`, and `inquiry`
- the evidence taxonomy (`literature_evidence`, `empirical_data_evidence`, `simulation_evidence`, `benchmark_evidence`, `expert_judgment`, `negative_result`)
- authored vs derived fields
- the skeptical default stance
- a worked example from question -> relation claim -> evidence -> updated belief

**Step 2: Cross-check against the approved design**

Re-read:

- `docs/plans/2026-03-16-claim-centric-uncertainty-design.md`

Confirm the canonical reference does not introduce extra ontology fog like `statement` or `proposition`.

**Step 3: Link the design doc to the canonical reference**

Add a short “Implemented By” or “Canonical Reference” note in:

- `docs/plans/2026-03-16-claim-centric-uncertainty-design.md`

pointing at `docs/claim-and-evidence-model.md`.

**Step 4: Review the prose for consistency**

Check that the reference consistently uses:

- “claims are uncertain”
- “evidence updates belief”
- “hypotheses are claim bundles or claim-like conjectures”

**Step 5: Commit**

```bash
git add docs/claim-and-evidence-model.md docs/plans/2026-03-16-claim-centric-uncertainty-design.md
git commit -m "docs: add claim-centric uncertainty model reference"
```

### Task 2: Define First-Class Relation-Claim And Evidence Semantics In The Graph Model

**Files:**
- Modify: `science-model/src/science_model/profiles/core.py`
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_graph_cli.py`
- Test: `science-tool/tests/test_graph_materialize.py`

**Step 1: Write the failing tests**

Add tests that require:

- a way to create or query `relation_claim`-style assertions
- evidence to target claims rather than hypotheses directly
- direct scientific edge authoring to be rejected or clearly marked as structural-only

Example shapes:

```python
def test_graph_add_relation_claim_creates_claim_with_subject_predicate_object() -> None:
    ...


def test_graph_add_scientific_edge_requires_claim_backing() -> None:
    ...
```

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
cd /home/keith/d/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q
```

Expected: new relation-claim tests fail because the CLI and store do not yet support claim-backed relation assertions.

**Step 3: Implement the minimal schema and CLI changes**

Update:

- `science-model/src/science_model/profiles/core.py`
- `science-tool/src/science_tool/graph/store.py`
- `science-tool/src/science_tool/cli.py`

Add or adapt:

- explicit `relation_claim` semantics, likely as a claim subtype or claim metadata
- explicit support for claim target references
- restrictions on `graph add edge` so uncertain scientific predicates are not authored as settled facts

Keep structural edges allowed where they are clearly non-epistemic.

**Step 4: Run tests to verify the implementation passes**

Run:

```bash
cd /home/keith/d/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q
```

Expected: the new graph CLI tests pass without breaking existing core graph-authoring behavior that still belongs in the tool.

**Step 5: Commit**

```bash
git add science-model/src/science_model/profiles/core.py science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py science-tool/tests/test_graph_materialize.py
git commit -m "feat: add claim-backed relation semantics"
```

### Task 3: Make Evidence Querying Claim-Centric

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing tests**

Add tests for:

- querying evidence by claim ID
- aggregating hypothesis evidence through linked claims rather than direct evidence-to-hypothesis edges
- preserving transitional compatibility for legacy direct evidence links, if retained

Example:

```python
def test_graph_evidence_returns_support_and_dispute_for_claim() -> None:
    ...
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /home/keith/d/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k evidence
```

Expected: FAIL because `query_evidence(...)` is still hypothesis-centric.

**Step 3: Implement the minimal claim-centric query path**

Update:

- `science-tool/src/science_tool/graph/store.py`
- `science-tool/src/science_tool/cli.py`

Make:

- `query_evidence(...)` claim-centric
- hypothesis evidence views aggregate across linked subordinate claims
- CLI help text explain the new model clearly

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /home/keith/d/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k evidence
```

Expected: PASS, with evidence now reported in terms of support/dispute on claims.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: make graph evidence queries claim-centric"
```

### Task 4: Replace Flat Confidence With Derived Claim Uncertainty

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/src/science_tool/graph/viz_template.py`
- Test: `science-tool/tests/test_graph_cli.py`
- Test: `science-tool/tests/test_graph_materialize.py`

**Step 1: Write the failing tests**

Add tests that require:

- uncertainty to derive from support/dispute structure
- contested claims to rank above simple low-confidence literals
- gap analysis to distinguish structural fragility from evidential fragility

Example:

```python
def test_query_uncertainty_prioritizes_contested_and_single_source_claims() -> None:
    ...
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /home/keith/d/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k "uncertainty or gaps"
```

Expected: FAIL because uncertainty is currently a flat status/confidence scan.

**Step 3: Implement the minimal derived scoring model**

Update:

- `science-tool/src/science_tool/graph/store.py`
- `science-tool/src/science_tool/graph/viz_template.py`

Implement:

- derived claim states such as `speculative`, `fragile`, `supported`, `well_supported`, `contested`
- support/dispute aggregation
- initial single-source and weak-evidence penalties
- dashboard panels for weakly supported, contested, and evidence-sparse claims

Do not add mathematically strict Bayesian updates yet.

**Step 4: Run tests to verify they pass**

Run:

```bash
cd /home/keith/d/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k "uncertainty or gaps"
```

Expected: PASS, with uncertainty now reflecting evidential structure instead of only scalar literals.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/graph/viz_template.py science-tool/tests/test_graph_cli.py science-tool/tests/test_graph_materialize.py
git commit -m "feat: derive claim uncertainty from evidence structure"
```

### Task 5: Attach Claims Explicitly To Inquiry And Causal Edges

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/src/science_tool/causal/export_pgmpy.py`
- Modify: `science-tool/src/science_tool/causal/export_chirho.py`
- Test: `science-tool/tests/test_inquiry_cli.py`
- Test: `science-tool/tests/test_causal_cli.py`

**Step 1: Write the failing tests**

Add tests requiring:

- inquiry or causal edges to reference supporting `relation_claim` IDs explicitly
- exporters to read attached claim bundles rather than guess by text matching
- ungrounded edges to be flagged in exporter output

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /home/keith/d/science/science-tool
uv run --frozen pytest tests/test_inquiry_cli.py tests/test_causal_cli.py -q
```

Expected: FAIL because exporter provenance is still heuristic.

**Step 3: Implement explicit claim attachment**

Update:

- `science-tool/src/science_tool/graph/store.py`
- `science-tool/src/science_tool/causal/export_pgmpy.py`
- `science-tool/src/science_tool/causal/export_chirho.py`

Add:

- explicit claim references on inquiry/causal edges
- exporter rendering of confidence/support/dispute metadata from attached claims
- warnings for ungrounded assumptions

**Step 4: Run tests to verify they pass**

Run:

```bash
cd /home/keith/d/science/science-tool
uv run --frozen pytest tests/test_inquiry_cli.py tests/test_causal_cli.py -q
```

Expected: PASS, with exporter comments and warnings grounded in explicit claim links.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/causal/export_pgmpy.py science-tool/src/science_tool/causal/export_chirho.py science-tool/tests/test_inquiry_cli.py science-tool/tests/test_causal_cli.py
git commit -m "feat: attach explicit claims to inquiry and causal edges"
```

### Task 6: Rewrite Commands And Templates Around Skeptical Claim Updates

**Files:**
- Modify: `commands/add-hypothesis.md`
- Modify: `commands/sketch-model.md`
- Modify: `commands/specify-model.md`
- Modify: `commands/interpret-results.md`
- Modify: `commands/compare-hypotheses.md`
- Modify: `commands/status.md`
- Modify: `templates/hypothesis.md`
- Modify: `templates/comparison.md`
- Modify: `templates/experiment.md`
- Modify: `templates/interpretation.md`
- Test: manual review

**Step 1: Write the first failing artifact checklist**

Create a checklist in the plan execution notes that each updated command/template must:

- stop teaching direct edge validation as default
- stop treating hypothesis status transitions as the main epistemic outcome
- introduce `claim`, `relation_claim`, support/dispute, and residual uncertainty where appropriate
- keep the workflow opt-in rather than forcing maximum formality

**Step 2: Review and rewrite the highest-value guidance surfaces**

Update the files above so that:

- hypotheses become claim bundles
- sketches capture tentative relation-claims
- specification formalizes claims and evidence
- interpretations update support/dispute and uncertainty
- comparisons surface contested claims and discriminating evidence
- status views present uncertainty-bearing claims, not settled edges

**Step 3: Update templates to capture the new data**

Add sections for:

- subclaims or relation-claims
- current uncertainty
- supporting evidence
- disputing evidence
- evidence needed to shift belief
- empirical vs simulation evidence where relevant

**Step 4: Manually review for terminology drift**

Search for language like:

```bash
rg -n "supported|refuted|confirmed|proved|every edge gets evidence|status transitions" commands templates
```

Resolve places where the old mental model remains the default.

**Step 5: Commit**

```bash
git add commands/add-hypothesis.md commands/sketch-model.md commands/specify-model.md commands/interpret-results.md commands/compare-hypotheses.md commands/status.md templates/hypothesis.md templates/comparison.md templates/experiment.md templates/interpretation.md
git commit -m "docs: align commands and templates with claim-centric uncertainty"
```

### Task 7: Update README And Global Skills To Teach The New Model

**Files:**
- Modify: `README.md`
- Modify: `skills/research/SKILL.md`
- Modify: `skills/writing/SKILL.md`
- Modify: `references/role-prompts/discussant.md`
- Test: manual review

**Step 1: Write the editorial checklist**

Require the updated language to teach:

- uncertainty by default
- claims as the primary units of belief
- evidence as support/dispute updates
- hypotheses as organizing conjectures, not automatically validated objects

**Step 2: Rewrite the main public-facing explanations**

Update:

- `README.md`
- `skills/research/SKILL.md`
- `skills/writing/SKILL.md`
- `references/role-prompts/discussant.md`

Remove or soften language that implies:

- direct proof from a single result
- direct edge truth
- discrete status ladders as the main epistemic model

**Step 3: Add references to the canonical model document**

Link:

- `docs/claim-and-evidence-model.md`

from the README and any skill or prompt where it would materially reduce terminology drift.

**Step 4: Manually review for consistency**

Run:

```bash
rg -n "proposed → under-investigation → supported/refuted/revised|demonstrates / establishes / confirms|validated edge|status transitions" README.md skills references
```

Expected: only deliberate, revised uses remain.

**Step 5: Commit**

```bash
git add README.md skills/research/SKILL.md skills/writing/SKILL.md references/role-prompts/discussant.md
git commit -m "docs: teach skeptical claim-centric reasoning model"
```

### Task 8: Add Neighborhood Uncertainty Prioritization

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/src/science_tool/graph/viz_template.py`
- Modify: `commands/next-steps.md`
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing tests**

Add tests for:

- neighborhood uncertainty ranking from nearby fragile or contested claims
- prioritization queries surfacing uncertain graph regions

Example:

```python
def test_query_gaps_reports_high_uncertainty_neighborhoods() -> None:
    ...
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /home/keith/d/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k gaps
```

Expected: FAIL because the current implementation only checks local connectivity/provenance/confidence.

**Step 3: Implement minimal neighborhood diffusion**

Update:

- `science-tool/src/science_tool/graph/store.py`
- `science-tool/src/science_tool/graph/viz_template.py`
- `commands/next-steps.md`

Add:

- a simple neighborhood uncertainty score based on nearby fragile/contested/single-source claims
- dashboard exposure for uncertainty hotspots
- next-steps guidance that treats high-uncertainty regions as likely high-value work areas

Keep the algorithm simple and explainable.

**Step 4: Run tests to verify they pass**

Run:

```bash
cd /home/keith/d/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k gaps
```

Expected: PASS, with gap analysis now exposing uncertain neighborhoods rather than only sparse nodes.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/graph/viz_template.py commands/next-steps.md science-tool/tests/test_graph_cli.py
git commit -m "feat: prioritize high-uncertainty graph neighborhoods"
```

### Task 9: Full Verification And Integration Review

**Files:**
- Modify: any files needed to resolve final review issues
- Test: `science-tool/tests/test_graph_cli.py`
- Test: `science-tool/tests/test_graph_materialize.py`
- Test: `science-tool/tests/test_inquiry_cli.py`
- Test: `science-tool/tests/test_causal_cli.py`

**Step 1: Run targeted integration tests**

Run:

```bash
cd /home/keith/d/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py tests/test_graph_materialize.py tests/test_inquiry_cli.py tests/test_causal_cli.py -q
```

Expected: PASS, with no regressions in graph, inquiry, or causal export behavior.

**Step 2: Run linting if available in the environment**

Run:

```bash
cd /home/keith/d/science/science-tool
uv run --frozen ruff check src/science_tool tests
```

Expected: PASS.
If `ruff` is missing from the environment, document that explicitly instead of pretending it ran.

**Step 3: Re-read the canonical model and updated guidance**

Check:

- `docs/claim-and-evidence-model.md`
- `README.md`
- updated `commands/`
- updated `templates/`
- updated `skills/`

Verify terminology is aligned and there is no obvious reintroduction of the old “edge as fact” model.

**Step 4: Record follow-up gaps**

Document any intentionally deferred items, especially:

- formal Bayesian updates
- full argument-chain modeling
- explicit premise nodes
- richer ontology bindings beyond the first SEPIO/ISA/STATO-informed pass

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: complete claim-centric uncertainty migration"
```
